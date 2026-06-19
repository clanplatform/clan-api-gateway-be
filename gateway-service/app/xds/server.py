"""
Envoy xDS v3 REST discovery server.

Envoy polls these endpoints to get dynamic Listener, Cluster, and Route config.
Protocol: https://www.envoyproxy.io/docs/envoy/latest/api-docs/xds_protocol#rest-json-polling-subscriptions
"""
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.xds_service import XdsService

router = APIRouter(tags=["xds"])

_CDS_TYPE = "type.googleapis.com/envoy.config.cluster.v3.Cluster"
_RDS_TYPE = "type.googleapis.com/envoy.config.route.v3.RouteConfiguration"
_LDS_TYPE = "type.googleapis.com/envoy.config.listener.v3.Listener"


@router.post("/v3/discovery:clusters")
async def cluster_discovery(
    body: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = XdsService(db)
    version = XdsService.current_version()
    # Return empty resources (304-equivalent) when Envoy already has this version
    if body.get("version_info") == version:
        return {"version_info": version, "resources": [], "type_url": _CDS_TYPE, "nonce": version}
    clusters = await svc.build_clusters()
    return {"version_info": version, "resources": clusters, "type_url": _CDS_TYPE, "nonce": version}


@router.post("/v3/discovery:routes")
async def route_discovery(
    body: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = XdsService(db)
    version = XdsService.current_version()
    if body.get("version_info") == version:
        return {"version_info": version, "resources": [], "type_url": _RDS_TYPE, "nonce": version}
    route_config = await svc.build_route_config()
    return {
        "version_info": version,
        "resources": [route_config],
        "type_url": _RDS_TYPE,
        "nonce": version,
    }


@router.post("/v3/discovery:listeners")
async def listener_discovery(
    body: dict = Body(default={}),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.core.config import get_settings
    settings = get_settings()

    version = XdsService.current_version()
    if body.get("version_info") == version:
        return {"version_info": version, "resources": [], "type_url": _LDS_TYPE, "nonce": version}

    listener = {
        "@type": _LDS_TYPE,
        "name": "main_listener",
        "address": {"socket_address": {"address": "0.0.0.0", "port_value": 8080}},
        "filter_chains": [
            {
                "filters": [
                    {
                        "name": "envoy.filters.network.http_connection_manager",
                        "typed_config": {
                            "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
                            "stat_prefix": "ingress_http",
                            "codec_type": "AUTO",
                            "use_remote_address": True,
                            "skip_xff_append": False,
                            "generate_request_id": True,
                            "preserve_external_request_id": True,
                            "rds": {
                                "config_source": {
                                    "api_config_source": {
                                        "api_type": "REST",
                                        "transport_api_version": "V3",
                                        "cluster_names": ["gateway_service"],
                                        "refresh_delay": settings.rds_refresh_delay,
                                    },
                                    "resource_api_version": "V3",
                                },
                                "route_config_name": "main_route",
                            },
                            "http_filters": [
                                # JWT authentication
                                {
                                    "name": "envoy.filters.http.jwt_authn",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.http.jwt_authn.v3.JwtAuthentication",
                                        "providers": {
                                            "clan_jwt": {
                                                "issuer": settings.jwt_issuer,
                                                "audiences": [settings.jwt_audience],
                                                "remote_jwks": {
                                                    "http_uri": {
                                                        "uri": settings.jwks_uri,
                                                        "cluster": settings.jwks_cluster,
                                                        "timeout": "5s",
                                                    },
                                                    "cache_duration": "300s",
                                                    "async_fetch": {"fast_listener": True},
                                                },
                                                "forward": True,
                                                "payload_in_metadata": "jwt_payload",
                                                "claim_to_headers": [
                                                    {"header_name": "x-tenant-id", "claim_name": "tenant_id"},
                                                    {"header_name": "x-user-id", "claim_name": "sub"},
                                                    {"header_name": "x-app-id", "claim_name": "app_id"},
                                                ],
                                            }
                                        },
                                        "rules": [
                                            {"match": {"prefix": "/health"}, "requires": {}},
                                            {"match": {"prefix": "/metrics"}, "requires": {}},
                                            {"match": {"prefix": "/v3/discovery"}, "requires": {}},
                                            {
                                                "match": {"prefix": "/"},
                                                "requires": {"provider_name": "clan_jwt"},
                                            },
                                        ],
                                    },
                                },
                                # Per-tenant rate limiting via headers (complementary to vhost rate_limits)
                                {
                                    "name": "envoy.filters.http.local_ratelimit",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.http.local_ratelimit.v3.LocalRateLimit",
                                        "stat_prefix": "local_rate_limiter",
                                        "token_bucket": {
                                            "max_tokens": 50_000,
                                            "tokens_per_fill": 50_000,
                                            "fill_interval": "1s",
                                        },
                                        "filter_enabled": {
                                            "runtime_key": "local_rate_limit_enabled",
                                            "default_value": {"numerator": 100, "denominator": "HUNDRED"},
                                        },
                                        "filter_enforced": {
                                            "runtime_key": "local_rate_limit_enforced",
                                            "default_value": {"numerator": 100, "denominator": "HUNDRED"},
                                        },
                                        "response_headers_to_add": [
                                            {
                                                "header": {"key": "x-ratelimit-limit", "value": "50000"},
                                                "keep_empty_value": False,
                                            }
                                        ],
                                    },
                                },
                                # CORS
                                {
                                    "name": "envoy.filters.http.cors",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.http.cors.v3.Cors"
                                    },
                                },
                                # Router must be last
                                {
                                    "name": "envoy.filters.http.router",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"
                                    },
                                },
                            ],
                            "access_log": [
                                {
                                    "name": "envoy.access_loggers.stdout",
                                    "typed_config": {
                                        "@type": "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog",
                                        "log_format": {
                                            "json_format": {
                                                "timestamp": "%START_TIME%",
                                                "method": "%REQ(:METHOD)%",
                                                "path": "%REQ(X-ENVOY-ORIGINAL-PATH?:PATH)%",
                                                "host": "%REQ(:AUTHORITY)%",
                                                "status": "%RESPONSE_CODE%",
                                                "duration_ms": "%DURATION%",
                                                "bytes_sent": "%BYTES_SENT%",
                                                "bytes_received": "%BYTES_RECEIVED%",
                                                "upstream_cluster": "%UPSTREAM_CLUSTER%",
                                                "upstream_host": "%UPSTREAM_HOST%",
                                                "request_id": "%REQ(X-REQUEST-ID)%",
                                                "tenant": "%REQ(X-TENANT-ID)%",
                                                "user_agent": "%REQ(USER-AGENT)%",
                                                "x_forwarded_for": "%REQ(X-FORWARDED-FOR)%",
                                                "response_flags": "%RESPONSE_FLAGS%",
                                            }
                                        },
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }

    return {
        "version_info": version,
        "resources": [listener],
        "type_url": _LDS_TYPE,
        "nonce": version,
    }
