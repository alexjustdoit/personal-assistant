import asyncio
import re
import feedparser
import httpx
import trafilatura


# Curated RSS feeds grouped by topic keyword.
# Topic matching is keyword-based: if any key appears in the user's topic string, those feeds are used.
FEED_LIBRARY: dict[str, list[str]] = {
    "technology": [
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.theverge.com/rss/index.xml",
        "https://techcrunch.com/feed/",
    ],
    "politics": [
        "https://feeds.npr.org/1014/rss.xml",            # NPR Politics
        "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    ],
    "seattle": [
        "https://komonews.com/feed",
        "https://www.king5.com/feeds/syndication/rss/news",
        "https://mynorthwest.com/feed/",
    ],
    "business": [
        "https://feeds.npr.org/1006/rss.xml",            # NPR Business
        "https://feeds.bbci.co.uk/news/business/rss.xml",
    ],
    "science": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    ],
    "health": [
        "https://feeds.npr.org/1128/rss.xml",            # NPR Health
        "https://feeds.bbci.co.uk/news/health/rss.xml",
    ],
    "world": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.npr.org/1004/rss.xml",            # NPR World
    ],
    # Fallback — used when no keyword matches
    "_general": [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://feeds.npr.org/1001/rss.xml",            # NPR Top Stories
    ],
}

MAX_ARTICLES_PER_FEED = 5
MAX_SCRAPE_PER_TOPIC = 3    # how many articles per topic to scrape for full text
MAX_ARTICLES_IN_PROMPT = 5  # cap articles sent to synthesis LLM (keeps context small for local models)
SCRAPE_TEXT_LIMIT = 1000    # chars of article body to pass to the LLM (was 1500)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/1.0)"}


def _feeds_for_topic(topic: str) -> list[str]:
    t = topic.lower()
    for key, feeds in FEED_LIBRARY.items():
        if key.startswith("_"):
            continue
        if key in t or t in key:
            return feeds
    return FEED_LIBRARY["_general"]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


async def _fetch_feed(client: httpx.AsyncClient, url: str, topic: str) -> list[dict]:
    """Fetch and parse a single RSS feed, returning article dicts with URLs."""
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        source = (feed.feed.get("title") or url).split(" - ")[0].strip()
        articles = []
        for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
            title = entry.get("title", "").strip()
            article_url = entry.get("link", "").strip()
            description = _strip_html(
                entry.get("summary") or entry.get("description") or ""
            )[:400]
            if not title:
                continue
            articles.append({
                "topic": topic,
                "title": title,
                "url": article_url,
                "source": source,
                "description": description,
                "full_text": "",   # populated by enrich_with_full_text()
            })
        return articles
    except Exception:
        return []


async def _scrape_article(client: httpx.AsyncClient, article: dict) -> dict:
    """
    Fetch article URL and extract full text with trafilatura.
    Falls back silently — article description is the backup.
    """
    url = article.get("url", "")
    if not url:
        return article
    try:
        resp = await client.get(url, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        text = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if text and len(text) > 150:
            article = dict(article)
            article["full_text"] = text[:SCRAPE_TEXT_LIMIT]
    except Exception:
        pass
    return article


async def get_rss_articles(topics: list[str]) -> list[dict]:
    """
    Fetch RSS headlines for each topic in parallel, then scrape full text
    for the top articles per topic. Returns enriched article dicts.
    """
    if not topics:
        return []

    # --- Phase 1: fetch all feeds in parallel ---
    async with httpx.AsyncClient(headers=_HEADERS) as client:
        feed_tasks = []
        seen_feeds: set[str] = set()
        for topic in topics[:5]:
            for feed_url in _feeds_for_topic(topic):
                if feed_url in seen_feeds:
                    continue
                seen_feeds.add(feed_url)
                feed_tasks.append(_fetch_feed(client, feed_url, topic))

        feed_results = await asyncio.gather(*feed_tasks)

    raw_articles: list[dict] = []
    for result in feed_results:
        raw_articles.extend(result)

    # --- Phase 2: scrape full text for top N per topic in parallel ---
    # Group and limit how many we'll scrape
    by_topic: dict[str, list[dict]] = {}
    for a in raw_articles:
        by_topic.setdefault(a["topic"], []).append(a)

    to_scrape: list[dict] = []
    no_scrape: list[dict] = []
    for topic_articles in by_topic.values():
        to_scrape.extend(topic_articles[:MAX_SCRAPE_PER_TOPIC])
        no_scrape.extend(topic_articles[MAX_SCRAPE_PER_TOPIC:])

    async with httpx.AsyncClient(headers=_HEADERS) as client:
        scraped = await asyncio.gather(*[_scrape_article(client, a) for a in to_scrape])

    return list(scraped) + no_scrape
