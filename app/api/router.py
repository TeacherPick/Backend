from fastapi import APIRouter
from sqlalchemy import text

from app.api import admin, auth, content, dm
from app.dependencies import Db

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(auth.admin_router)
router.include_router(content.router)
router.include_router(content.instructors)
router.include_router(content.my_content)
router.include_router(dm.router)
router.include_router(admin.router)


@router.get("/health", tags=["상태"])
def health(db: Db) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
