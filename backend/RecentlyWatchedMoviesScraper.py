import feedparser
from datetime import datetime, timedelta

BASE_FEED = "https://letterboxd.com/{username}/rss/"

def fetch_recent_watches(username: str, number_of_days: int) -> list[int]:
    url = build_feed_url(username)
    feed = feedparser.parse(url)

    if getattr(feed, 'status', None) not in (200, None) or feed.bozo:
        raise RuntimeError(f"RSS fetch failed or invalid feed for {url}")

    entries: list[int] = []
    for entry in feed.entries:
        watched_date = entry.get("letterboxd_watcheddate")
        if is_less_than_n_days_ago(watched_date, n=number_of_days):
            entries.append(int(entry.get("tmdb_movieid")))
    return entries

def build_feed_url(username: str) -> str:
    return BASE_FEED.format(username=username.strip())

def is_less_than_n_days_ago(date_str: str, n: int = 90) -> bool:
    """Check if a date string (YYYY-MM-DD) is within the last n days."""
    if not date_str:
        return False
    try:
        watched_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        n_days_ago = datetime.now().date() - timedelta(days=n)
        return watched_date >= n_days_ago
    except ValueError:
        return False