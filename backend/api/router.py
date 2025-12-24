from fastapi import APIRouter

from api.accounts import router as accounts_router
from api.proxy import router as proxy_router
from api.groups import router as groups_router
from api.tags import router as tags_router

api_router = APIRouter()

api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(proxy_router, prefix="/proxy", tags=["proxy"])
api_router.include_router(groups_router, prefix="/groups", tags=["groups"])
api_router.include_router(tags_router, prefix="/tags", tags=["tags"])
