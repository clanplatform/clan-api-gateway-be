import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app, Counter, Histogram
from app.core.config import get_settings
from app.core.database import init_db
from app.api.v1.router import router as v1_router
from app.xds.server import router as xds_router

settings = get_settings()
log = structlog.get_logger()

REQUEST_COUNT = Counter("gateway_requests_total", "Total HTTP requests", ["method", "path", "status"])
REQUEST_LATENCY = Histogram("gateway_request_duration_seconds", "HTTP request latency", ["method", "path"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("gateway.startup", environment=settings.environment)
    await init_db()
    yield
    log.info("gateway.shutdown")


app = FastAPI(
    title="Clan API Gateway — Control Plane",
    description="Manages tenants, applications, and Envoy xDS configuration for 1000+ SaaS apps.",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time
    path = request.url.path
    method = request.method
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    REQUEST_COUNT.labels(method=method, path=path, status=response.status_code).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
    response.headers["x-request-id"] = request.headers.get("x-request-id", "")
    return response


app.include_router(v1_router)
app.include_router(xds_router)

if settings.metrics_enabled:
    app.mount("/metrics", make_asgi_app())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
