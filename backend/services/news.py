import httpx
from backend.config import config


class NewsService:
    def __init__(self):
        cfg = config.get("news", {})
        self.enabled = cfg.get("enabled", False)
        self.api_key = cfg.get("api_key", "")
        self.topics = cfg.get("topics", [])

    async def get_digest(self) -> list[str]:
        if not self.enabled or not self.api_key or not self.topics:
            return []
        headlines = []
        async with httpx.AsyncClient() as client:
            for topic in self.topics[:5]:  # cap at 5 topics
                try:
                    res = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.api_key,
                            "query": f"latest news {topic}",
                            "search_depth": "basic",
                            "max_results": 2,
                        },
                        timeout=10,
                    )
                    res.raise_for_status()
                    data = res.json()
                    for result in data.get("results", []):
                        title = result.get("title", "").strip()
                        if title:
                            headlines.append(f"[{topic}] {title}")
                except Exception:
                    continue
        return headlines


news_service = NewsService()
