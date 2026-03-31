import httpx
from backend.config import config


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    api_key = config.get("news", {}).get("api_key", "")
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": True,
                },
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()

        results = []
        if data.get("answer"):
            results.append({"title": "Summary", "content": data["answer"], "url": ""})
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "content": r.get("content", "")[:400],
                "url": r.get("url", ""),
            })
        return results
    except Exception:
        return []


def search_enabled() -> bool:
    return bool(config.get("news", {}).get("api_key", ""))
