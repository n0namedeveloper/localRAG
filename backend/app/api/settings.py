from fastapi import APIRouter
from app.core.settings_manager import settings_manager, AppSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("", response_model=AppSettings)
async def get_settings():
    return settings_manager.get()

@router.post("", response_model=AppSettings)
async def update_settings(settings: AppSettings):
    settings_manager.save(settings)
    return settings
