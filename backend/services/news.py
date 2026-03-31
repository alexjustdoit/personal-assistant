import httpx
from urllib.parse import urlparse
from backend.config import config


class NewsService:
    def __init__(self):
        cfg = config.get("news", {})
        self.enabled = cfg.get("enabled", False)
        self.api_key = cfg.get("api_key", "")
        self.topics = cfg.get("topics", [])

    async def get_articles(self) -> list[dict]:
        """Return articles with title, url, source, and full content for LLM processing."""
        if not self.enabled or not self.api_key or not self.topics:
            return []
        articles = []
        async with httpx.AsyncClient() as client:
            for topic in self.topics[:5]:
                try:
                    res = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": self.api_key,
                            "query": f"latest news {topic}",
                            "search_depth": "basic",
                            "max_results": 3,
                        },
                        timeout=10,
                    )
                    res.raise_for_status()
                    data = res.json()
                    for result in data.get("results", []):
                        title = result.get("title", "").strip()
                        url = result.get("url", "").strip()
                        content = result.get("content", "").strip()
                        if not title or not url:
                            continue
                        source = urlparse(url).netloc.replace("www.", "")
                        articles.append({
                            "topic": topic,
                            "title": title,
                            "url": url,
                            "source": source,
                            "content": content,   # full content for LLM
                            "insight": "",        # filled in by _curate_news
                        })
                except Exception:
                    continue
        return articles

    async def get_digest(self) -> list[str]:
        """Plain headline strings — used by the scheduled ntfy briefing."""
        articles = await self.get_articles()
        return [f"[{a['topic']}] {a['title']}" for a in articles]


news_service = NewsService()
