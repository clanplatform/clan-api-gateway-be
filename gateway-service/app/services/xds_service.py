import time
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.application import Application
from app.models.tenant import Tenant


class XdsService:
    """Builds Envoy xDS v3 JSON resources from the database and tracks config version."""

    _version: int = int(time.time() * 1000)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @classmethod
    def current_version(cls) -> str:
        return str(cls._version)

    @classmethod
    async def bump_version(cls) -> None:
        cls._version = int(time.time() * 1000)

    # ── CDS ──────────────────────────────────────────────────────────────────

    async def build_clusters(self) -> list[dict]:
        result = await self.db.execute(select(Application).where(Application.is_active.is_(True)))
        apps = result.scalars().all()

        clusters: list[dict] = []
        for app in apps:
            cluster: dict = {
                "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
                "name": f"app_{app.id}",
                "connect_timeout": "5s",
                "type": "STRICT_DNS",
                "dns_lookup_family": "V4_ONLY",
                "respect_dns_ttl": True,
                "load_assignment": {
                    "cluster_name": f"app_{app.id}",
                    "endpoints": [
                        {
                            "lb_endpoints": [
                                {
                                    "endpoint": {
                                        "address": {
                                            "socket_address": {
                                                "address": app.upstream_host,
                                                "port_value": app.upstream_port,
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    ],
                },
                "circuit_breakers": {
                    "thresholds": [
                        {
                            "priority": "DEFAULT",
                            "max_connections": 1000,
                            "max_pending_requests": 1000,
                            "max_requests": 1000,
                            "max_retries": 100,
                        }
                    ]
                },
                "outlier_detection": {
                    "consecutive_5xx": 5,
                    "interval": "10s",
                    "base_ejection_time": "30s",
                    "max_ejection_percent": 50,
                },
                "health_checks": [],
            }
            if app.upstream_tls:
                cluster["transport_socket"] = {
                    "name": "envoy.transport_sockets.tls",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext",
                        "sni": app.upstream_host,
                    },
                }
            clusters.append(cluster)

        return clusters

    # ── RDS ──────────────────────────────────────────────────────────────────

    async def build_route_config(self) -> dict:
        result = await self.db.execute(select(Application).where(Application.is_active.is_(True)))
        apps = result.scalars().all()

        tenant_map: dict[str, list[Application]] = {}
        for app in apps:
            tenant_map.setdefault(str(app.tenant_id), []).append(app)

        virtual_hosts: list[dict] = []

        for tenant_id_str, tenant_apps in tenant_map.items():
            tenant_result = await self.db.execute(
                select(Tenant).where(Tenant.id == uuid.UUID(tenant_id_str))
            )
            tenant = tenant_result.scalar_one_or_none()
            if not tenant or not tenant.is_active:
                continue

            routes: list[dict] = []
            all_cors_origins: set[str] = set()

            # Collect (route, app) pairs across ALL apps then sort globally so that
            # longer prefixes always appear before shorter ones in Envoy's route table
            # (e.g. /api/v1/auth/users must precede /api/v1/auth).
            all_route_app_pairs: list[tuple] = []
            for app in tenant_apps:
                all_cors_origins.update(app.cors_origins or [])
                for route in app.route_configs:
                    all_route_app_pairs.append((route, app))

            for route, app in sorted(all_route_app_pairs, key=lambda x: -len(x[0].path_prefix)):
                route_entry: dict = {
                    "match": {"prefix": route.path_prefix},
                    "route": {
                        "cluster": f"app_{app.id}",
                        "timeout": f"{route.timeout_ms / 1000:.3f}s",
                        "retry_policy": {
                            "retry_on": "5xx,gateway-error,connect-failure,retriable-4xx",
                            "num_retries": route.retry_attempts,
                            "per_try_timeout": f"{route.timeout_ms / 1000:.3f}s",
                            "retry_back_off": {"base_interval": "0.025s", "max_interval": "1s"},
                        },
                    },
                }
                if route.prefix_rewrite:
                    route_entry["route"]["prefix_rewrite"] = route.prefix_rewrite
                if route.headers_to_add:
                    route_entry["request_headers_to_add"] = [
                        {"header": {"key": k, "value": v}, "keep_empty_value": False}
                        for k, v in route.headers_to_add.items()
                    ]
                # Inject tenant + app metadata so upstream services don't need auth re-parse
                route_entry.setdefault("request_headers_to_add", []).extend([
                    {"header": {"key": "x-tenant-id", "value": str(tenant.id)}, "keep_empty_value": False},
                    {"header": {"key": "x-tenant-slug", "value": tenant.slug}, "keep_empty_value": False},
                    {"header": {"key": "x-app-id", "value": str(app.id)}, "keep_empty_value": False},
                ])
                routes.append(route_entry)

            if not routes:
                continue

            cors_config: dict
            if all_cors_origins:
                cors_config = {
                    "allow_origin_string_match": [{"exact": o} for o in sorted(all_cors_origins)],
                    "allow_methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD",
                    "allow_headers": "authorization,content-type,x-request-id,x-tenant-id",
                    "expose_headers": "x-request-id,x-ratelimit-limit,x-ratelimit-remaining",
                    "max_age": "86400",
                    "allow_credentials": True,
                }
            else:
                cors_config = {
                    "allow_origin_string_match": [{"safe_regex": {"regex": ".*"}}],
                    "allow_methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS,HEAD",
                    "allow_headers": "authorization,content-type,x-request-id",
                    "expose_headers": "x-request-id,x-ratelimit-limit,x-ratelimit-remaining",
                    "max_age": "86400",
                    "allow_credentials": False,
                }

            virtual_hosts.append({
                "name": f"tenant_{tenant.slug}",
                "domains": [
                    f"{tenant.slug}.{_GATEWAY_DOMAIN}",
                    f"{tenant.slug}.{_GATEWAY_DOMAIN}:*",
                ],
                "routes": routes,
                "cors": cors_config,
                "rate_limits": [
                    {
                        "actions": [
                            {"remote_address": {}},
                            {"generic_key": {"descriptor_value": tenant.slug}},
                        ]
                    }
                ],
            })

        # Catch-all: unknown tenant → 404
        virtual_hosts.append({
            "name": "fallback",
            "domains": ["*"],
            "routes": [
                {
                    "match": {"prefix": "/health"},
                    "direct_response": {"status": 200, "body": {"inline_string": '{"status":"ok"}'}},
                },
                {
                    "match": {"prefix": "/"},
                    "direct_response": {
                        "status": 404,
                        "body": {"inline_string": '{"detail":"tenant not found"}'},
                    },
                    "response_headers_to_add": [
                        {"header": {"key": "content-type", "value": "application/json"}, "keep_empty_value": False}
                    ],
                },
            ],
        })

        return {
            "@type": "type.googleapis.com/envoy.config.route.v3.RouteConfiguration",
            "name": "main_route",
            "virtual_hosts": virtual_hosts,
            "request_headers_to_add": [
                {"header": {"key": "x-forwarded-host", "value": "%REQ(:AUTHORITY)%"}, "keep_empty_value": False}
            ],
        }


_GATEWAY_DOMAIN = "api.example.com"
