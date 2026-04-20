from fastapi import APIRouter
from notifications.service import get_alert_log

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(limit: int = 50):
    log = get_alert_log()
    return list(reversed(log))[-limit:]
