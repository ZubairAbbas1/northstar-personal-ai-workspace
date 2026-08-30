from fastapi import APIRouter
from backend.api.v1 import (
    ai_settings,
    assistant,
    auth,
    calendar,
    inbox,
    integrations,
    memories,
    notifications,
    projects,
    search,
    tasks,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(inbox.router)
api_router.include_router(ai_settings.router)
api_router.include_router(integrations.router)
api_router.include_router(tasks.router)
api_router.include_router(projects.router)
api_router.include_router(notifications.router)
api_router.include_router(assistant.router)
api_router.include_router(calendar.router)
api_router.include_router(memories.router)
api_router.include_router(search.router)
