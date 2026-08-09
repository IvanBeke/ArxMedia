from celery import shared_task
from django.utils import timezone


@shared_task(name="tracking.heartbeat")
def heartbeat() -> dict[str, str]:
    now = timezone.now().isoformat()
    return {"status": "ok", "timestamp": now}
