import asyncio
import feedparser
import httpx
from datetime import datetime, timezone


# Curated RSS feeds grouped by topic keyword.
# Topic matching is keyword-based: if any key appears in the user's topic string, those feeds are used.
FEED_LIBRARY: dict[str, list[str]] = {
    "technology": [
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.theverge.com/rss/index.xml",
        "https://techcrunch.com/feed/",
    ],
    "politics": [
        "https://feeds.npr.org/1014/rss.xml",           # NPR Politics
        "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    ],
    "seattle": [
        "https://komonews.com/feed",
        "https://www.king5.com/feeds/syndication/rss/news",
        "https://mynorthwest.com/feed/",
    ],
    "business": [
        "https://feeds.npr.org/1006/rss.xml",           # NPR Business
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
    "science": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    ],
    "health": [
        "https://feeds.npr.org/1128/rss.xml",           # NPR Health
        "https://feeds.bbci.co.uk/news/health/rss.xml",
    ],
    "world": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.npr.org/1004/rss.xml",           # NPR World
    ],
    # Fallback — used when no keyword matches
    "_general": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://feeds.npr.org/1001/rss.xml",           # NPR Top Stories
    ],
}

MAX_ARTICLES_PER_FEED = 5


def _feeds_for_topic(topic: str) -> list[str]:
    t = topic.lower()
    for key, feeds in FEED_LIBRARY.items():
        if key.startswith("_"):
            continue
        if key in t or t in key:
            return feeds
    return FEED_LIBRARY["_general"]


async def _fetch_feed(client: httpx.AsyncClient, url: str, topic: str) -> list[dict]:
    """Fetch and parse a single RSS feed, returning a list of article dicts."""
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        articles = []
        # Derive a clean source name from the feed title or URL
        source = (feed.feed.get("title") or url).split(" - ")[0].strip()
        for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
            title = entry.get("title", "").strip()
            description = (entry.get("summary") or entry.get("description") or "").strip()
            # Strip any HTML tags from description
            import re
            description = re.sub(r"<[^>]+>", "", description)[:300].strip()
            if not title:
                continue
            articles.append({
                "topic": topic,
                "title": title,
                "description": description,
                "source": source,
            })
        return articles
    except Exception:
        return []


async def get_rss_articles(topics: list[str]) -> list[dict]:
    """
    Fetch RSS headlines for each topic in parallel.
    Returns list of {topic, title, description, source} dicts.
    """
    if not topics:
        return []

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/1.0)"}) as client:
        tasks = []
        task_topics = []
        seen_feeds: set[str] = set()

        for topic in topics[:5]:
            feeds = _feeds_for_topic(topic)
            for feed_url in feeds:
                if feed_url in seen_feeds:
                    continue
                seen_feeds.add(feed_url)
                tasks.append(_fetch_feed(client, feed_url, topic))
                task_topics.append(topic)

        results = await asyncio.gather(*tasks)

    articles = []
    for result in results:
        articles.extend(result)
    return articles
