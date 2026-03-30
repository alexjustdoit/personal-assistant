import httpx
from backend.config import config


class NotificationService:
    def __init__(self):
        cfg = config.get("notifications", {})
        self.ntfy_url = cfg.get("ntfy_url", "https://ntfy.sh").rstrip("/")
        self.ntfy_topic = cfg.get("ntfy_topic", "")

    async def send(self, title: str, body: str, priority: str = "default") -> bool:
        if not self.ntfy_topic:
            return False
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.ntfy_url}/{self.ntfy_topic}",
                    content=body,
                    headers={
                        "Title": title,
                        "Priority": priority,
                    },
                    timeout=10,
                )
                return res.status_code == 200
        except Exception:
            return False


notification_service = NotificationService()
