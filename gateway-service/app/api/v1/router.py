from fastapi import APIRouter
from app.api.v1 import health, tenants, applications, sync

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(tenants.router)
router.include_router(applications.router)
router.include_router(sync.router)
