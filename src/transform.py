"""
TRMNL Cinema: serverless transform.

TRMNL runs `run(input)` on its own servers on every refresh (Python 3.12 with
`requests` and the standard library, 5 s and 128 MB per run). It scrapes the
programme of one city from cinema.de, ranks the films by their Letterboxd rating,
optionally hides films the user logged on Letterboxd recently, and returns the
merge variables for the Liquid views.

Letterboxd results are cached in TRMNL's Saved State (8 KB per install), so a run
only looks up films that are new in the programme.
"""
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock
from html.parser import HTMLParser

import requests

CINEMA_URL = "https://www.cinema.de/kino/kinoprogramm/{city}"
LETTERBOXD_SEARCH_URL = "https://api.letterboxd.com/api/v0/search"
LETTERBOXD_RSS_URL = "https://letterboxd.com/{username}/rss/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

TIME_BUDGET_S = 3.0       # TRMNL stops a run after 5 s, Python's start-up included
REQUEST_TIMEOUT = (2, 3)  # seconds to connect, seconds between received bytes
LOOKUP_WORKERS = 10
MAX_MOVIES = 3
POSTER_MIN_WIDTH = 300
DEFAULT_RECENT_DAYS = 180
CACHE_MAX_AGE_DAYS = 3    # ratings of new releases still move, so refresh them now and then
STATE_LIMIT_BYTES = 7500  # Saved State holds at most 8192 bytes
STATE_VERSION = 1

# Recurring events and special screenings that aren't films
MOVIES_TO_IGNORE = {
    "Sneak Preview", "CineSneak", "Sonderveranstaltung", "Dokumentarfilm(e)",
    "Shorts Attack - Kurzfilme", "Sondervorstellung",
}

# Parts of the tag groups cinema.de appends to titles, e.g. "(OmU)", "(Deutsch/MXP 2D)",
# "(OV/70 mm)" or a trailing "3D", mapped to the short tags shown on screen
TAG_ALIASES = {
    "OmU": "OmU", "OmeU": "OmeU", "OF": "OV", "OV": "OV", "3D": "3D", "HFR": "HFR", "IMAX": "IMAX",
    "MXP": "MXP", "PLF": "PLF", "70 mm": "70mm", "70mm": "70mm",
    "Türkische Sprachfassung": "TUR", "Tükische Sprachfassung": "TUR", "Ukrainische Sprachfassung": "UKR",
}
IGNORED_TAG_PARTS = {"Deutsch", "2D", "deutsche Dialoge, englische Songs"}
TRAILING_TAG_GROUP = re.compile(r"\s*(\([^()]*\)|\b3D)\s*$")
SHOWTIME = re.compile(r"\d\d:\d\d")
PAGE_TITLE = re.compile(r"Kinoprogramm für (.+?) - ")

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class CinemaError(Exception):
    """A problem worth showing on the screen instead of the programme."""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(input):
    trmnl = input.get("trmnl") or {}
    fields = (trmnl.get("plugin_settings") or {}).get("custom_fields_values") or {}
    state = trmnl.get("state") or {}
    previous = trmnl.get("previous_merge_variables") or {}
    now = german_now()
    try:
        return build_screen(fields, state, now, time.monotonic() + TIME_BUDGET_S)
    except Exception as e:
        message = str(e) if isinstance(e, CinemaError) else "Something went wrong: %s" % type(e).__name__
        result = reuse_previous(previous, now) or {"city": fields.get("city", ""), "movies": []}
        result.update(error=message, trmnl_state=state)
        return result


def build_screen(fields, state, now, deadline):
    slug = city_slug(fields.get("city", ""))
    if not slug:
        raise CinemaError("Set your city in the plugin settings.")
    username = letterboxd_username(fields.get("letterboxd_username", ""))
    recent_days = to_int(fields.get("recent_days"), DEFAULT_RECENT_DAYS)
    cinema_filter = [part.strip().lower() for part in str(fields.get("cinemas") or "").split(",") if part.strip()]

    pool = ThreadPoolExecutor(max_workers=LOOKUP_WORKERS)
    try:
        watched_job = pool.submit(fetch_recent_watches, username, now.date(), recent_days) if username else None

        day = "today"
        city, films = fetch_programme(slug)
        films = only_upcoming(only_cinemas(films, cinema_filter), now.strftime("%H:%M"))
        if not films:
            # Today's last screening has started: show tomorrow's programme instead
            day = "tomorrow"
            city, films = fetch_programme(slug, now.date() + timedelta(days=1))
            films = only_cinemas(films, cinema_filter)

        cache = load_cache(state)
        today = now.date().toordinal()
        by_popularity = sorted(films, key=lambda title: -screening_count(films[title]))
        stale = [t for t in by_popularity if t not in cache or today - cache[t][3] > CACHE_MAX_AGE_DAYS]
        cache.update(look_up_films(pool, stale, deadline, today))

        watched = set()
        if watched_job:
            done, _ = wait([watched_job], timeout=max(0, deadline - time.monotonic()))
            watched = watched_job.result() if done and not watched_job.exception() else set()

        ranked = rank(films, cache, watched)
        top = ranked[:MAX_MOVIES]
        # Posters of films outside the top are dropped from the cache when it runs full
        missing_posters = [t for t in top if cache.get(t) and cache[t][0] is not None and not cache[t][2]]
        cache.update(look_up_films(pool, missing_posters, deadline, today))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return {
        "city": city,
        "day": day,
        "date": (now.date() + timedelta(days=1 if day == "tomorrow" else 0)).isoformat(),
        "updated_at": now.strftime("%H:%M"),
        "movies": [movie_view(title, films[title], cache.get(title)) for title in top],
        "error": "",
        "trmnl_state": build_state(cache, set(films), set(top)),
    }


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

def german_now(utc_now=None):
    """Current local time in Germany.

    TRMNL's runtime has no time zone database, so the EU rule is applied by hand:
    summer time runs from the last Sunday of March to the last Sunday of October,
    switching at 01:00 UTC.
    """
    utc_now = utc_now or datetime.now(timezone.utc)

    def last_sunday(month):
        last_day = date(utc_now.year, month, 31)  # March and October both have 31 days
        return last_day - timedelta(days=(last_day.weekday() + 1) % 7)

    summer_start = datetime.combine(last_sunday(3), clock(1), tzinfo=timezone.utc)
    summer_end = datetime.combine(last_sunday(10), clock(1), tzinfo=timezone.utc)
    offset = 2 if summer_start <= utc_now < summer_end else 1
    return (utc_now + timedelta(hours=offset)).replace(tzinfo=None)


def city_slug(city):
    """Turn "München", "Frankfurt am Main" or a cinema.de URL into cinema.de's URL slug."""
    city = str(city or "").strip()
    url = re.search(r"cinema\.de/kino/kinoprogramm/([A-Za-z0-9-]+)", city)
    if url:
        return url.group(1).lower()
    slug = city.lower()
    for umlaut, spelled in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        slug = slug.replace(umlaut, spelled)
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def letterboxd_username(value):
    """Accept "name", "@name" or a letterboxd.com profile URL."""
    value = str(value or "").strip()
    url = re.search(r"letterboxd\.com/([A-Za-z0-9_]+)", value)
    return url.group(1) if url else value.lstrip("@")


def to_int(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# cinema.de
# ---------------------------------------------------------------------------

# One connection pool for all lookups, so a run needs a TLS handshake per worker instead of per film
SESSION = requests.Session()
SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=LOOKUP_WORKERS))


def http_get(url, params=None):
    return SESSION.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)


def fetch_programme(slug, day=None):
    """Return (city display name, {title: {cinema: [screening, ...]}}) for one day."""
    try:
        response = http_get(CINEMA_URL.format(city=slug), {"day": day.isoformat()} if day else None)
    except requests.RequestException:
        raise CinemaError("cinema.de is not reachable right now.")
    if response.status_code == 404:
        raise CinemaError(unknown_city_message(slug))
    if response.status_code != 200:
        raise CinemaError("cinema.de answered with error %s." % response.status_code)
    city, cinema_count, films = parse_programme(response.text)
    if not cinema_count:
        raise CinemaError(unknown_city_message(slug))
    return city or slug, films


def unknown_city_message(slug):
    return ("cinema.de has no cinemas for '%s'. Use the city as it appears in the cinema.de URL, "
            "e.g. 'halle-saale' or 'freiburg-im-breisgau'." % slug)


class ProgrammeParser(HTMLParser):
    """Collects [cinema, title, [times]] rows from a cinema.de city page by CSS class."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.page_title = ""
        self.cinemas = []
        self.rows = []
        self._row = None
        self._field = None
        self._depth = 0
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if self._field:
            if tag not in VOID_TAGS:
                self._depth += 1
            return
        classes = (dict(attrs).get("class") or "").split()
        if tag == "title" and not self.page_title:  # inline SVG icons have <title>s too
            self._start("page_title")
        elif tag == "a" and "heading-he" in classes:
            self._start("cinema")
        elif tag == "div" and "movie" in classes:
            self._start("title")
        elif tag == "span" and "cinde-tag" in classes:
            self._start("time")

    def _start(self, field):
        self._field, self._depth, self._buf = field, 1, []

    def handle_data(self, data):
        if self._field:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if not self._field or tag in VOID_TAGS:
            return
        self._depth -= 1
        if self._depth:
            return
        text = " ".join("".join(self._buf).split())
        field, self._field = self._field, None
        if field == "page_title":
            self.page_title = text
        elif field == "cinema":
            self.cinemas.append(text)
        elif field == "title":
            self._row = [self.cinemas[-1] if self.cinemas else "", text, []]
            self.rows.append(self._row)
        elif field == "time" and self._row is not None:
            self._row[2].append(text)


def parse_programme(html):
    """Return (city display name, number of cinemas, {title: {cinema: [screening, ...]}})."""
    parser = ProgrammeParser()
    parser.feed(html)
    parser.close()

    films = {}
    for cinema, raw_title, times in parser.rows:
        title, tags = split_title_tags(raw_title)
        times = [t for t in times if SHOWTIME.fullmatch(t)]
        if not cinema or not title or not times or title in MOVIES_TO_IGNORE:
            continue
        screenings = films.setdefault(title, {}).setdefault(cinema, [])
        screenings.extend({"time": t, "tags": tags} for t in times)
    for cinemas in films.values():
        for screenings in cinemas.values():
            screenings.sort(key=lambda s: s["time"])

    city = PAGE_TITLE.search(parser.page_title)
    return (city.group(1) if city else ""), len(parser.cinemas), films


def split_title_tags(raw_title):
    """Split "Avatar (Deutsch/HFR 3D)" into ("Avatar", ["HFR", "3D"])."""
    title, tags = raw_title.strip(), []
    while True:
        match = TRAILING_TAG_GROUP.search(title)
        group_tags = parse_tag_group(match.group(1).strip("()")) if match else None
        if group_tags is None:
            break
        tags = group_tags + tags
        title = title[:match.start()].rstrip()
    return title, list(dict.fromkeys(tags))


def parse_tag_group(group):
    """Tags in one bracket group, or None if it is part of the title like "(The Doll)"."""
    tags = []
    for part in group.split("/"):
        part = part.strip()
        if part in TAG_ALIASES:
            tags.append(TAG_ALIASES[part])
        elif part not in IGNORED_TAG_PARTS:
            words = part.split()
            if not words or not all(w in TAG_ALIASES or w in IGNORED_TAG_PARTS for w in words):
                return None
            tags.extend(TAG_ALIASES[w] for w in words if w in TAG_ALIASES)
    return tags


def only_cinemas(films, cinema_filter):
    if not cinema_filter:
        return films
    kept = {}
    for title, cinemas in films.items():
        matching = {c: s for c, s in cinemas.items() if any(part in c.lower() for part in cinema_filter)}
        if matching:
            kept[title] = matching
    return kept


def only_upcoming(films, now_hhmm):
    kept = {}
    for title, cinemas in films.items():
        upcoming = {c: [s for s in screenings if s["time"] >= now_hhmm] for c, screenings in cinemas.items()}
        upcoming = {c: s for c, s in upcoming.items() if s}
        if upcoming:
            kept[title] = upcoming
    return kept


def screening_count(cinemas):
    return sum(len(screenings) for screenings in cinemas.values())


# ---------------------------------------------------------------------------
# Letterboxd
# ---------------------------------------------------------------------------

def look_up_films(pool, titles, deadline, today):
    """Search Letterboxd for several films in parallel until the deadline.

    Returns {title: [rating, tmdb_id, poster_url, day]} for every lookup that finished;
    films Letterboxd doesn't know are cached as [None, None, None, day] too.
    """
    if not titles or time.monotonic() >= deadline:
        return {}
    jobs = {pool.submit(search_letterboxd, title): title for title in titles}
    done, _ = wait(jobs, timeout=max(0, deadline - time.monotonic()))
    results = {}
    for job in done:
        if job.exception() is None:
            film = job.result()
            results[jobs[job]] = [
                round(film["rating"], 2) if film.get("rating") is not None else None,
                film.get("tmdb_id"),
                film.get("poster_url"),
                today,
            ] if film else [None, None, None, today]
    return results


def search_letterboxd(title):
    response = http_get(LETTERBOXD_SEARCH_URL, {"input": title, "include": "FilmSearchItem"})
    response.raise_for_status()
    film = select_search_result(response.json())
    if not film:
        return None
    return {"rating": film.get("rating"), "tmdb_id": extract_tmdb_id(film), "poster_url": extract_poster_url(film)}


def select_search_result(response):
    items = [item for item in response.get("items") or [] if item.get("film")]
    if not items:
        return None
    # Drop weak matches, then prefer the newest of the top three: that's the one in cinemas
    best_score = max(item.get("score") or 0 for item in items)
    candidates = [item["film"] for item in items if (item.get("score") or 0) >= 0.5 * best_score][:3]
    return max(candidates, key=lambda film: film.get("releaseYear") or 0)


def extract_poster_url(film):
    """Smallest poster that is still sharp on TRMNL X."""
    try:
        sizes = sorted(film["poster"]["sizes"], key=lambda size: size.get("width") or 0)
    except (KeyError, TypeError, AttributeError):
        return None
    for size in sizes:
        if (size.get("width") or 0) >= POSTER_MIN_WIDTH:
            return size.get("url")
    return sizes[-1].get("url") if sizes else None


def extract_tmdb_id(film):
    for link in film.get("links") or []:
        if link.get("type") == "tmdb":
            try:
                return int(link["id"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def fetch_recent_watches(username, today, days):
    """TMDB ids of the films the user logged on Letterboxd within the last `days` days."""
    response = http_get(LETTERBOXD_RSS_URL.format(username=username))
    response.raise_for_status()
    return parse_recent_watches(response.content, today, days)


def parse_recent_watches(xml, today, days):
    watched = set()
    for item in ET.fromstring(xml).iter("item"):
        values = {child.tag.split("}")[-1]: (child.text or "").strip() for child in item}
        # TV shows carry "tvId" instead of "movieId"; they aren't in cinemas
        if not values.get("movieId") or not values.get("watchedDate"):
            continue
        try:
            watched_on = date.fromisoformat(values["watchedDate"])
            if (today - watched_on).days <= days:
                watched.add(int(values["movieId"]))
        except ValueError:
            continue
    return watched


# ---------------------------------------------------------------------------
# Ranking and output
# ---------------------------------------------------------------------------

def rank(films, cache, watched):
    """Titles by Letterboxd rating; unrated films last, ties broken by number of screenings."""
    def info(title):
        return cache.get(title) or [None, None, None, None]

    titles = [t for t in films if info(t)[1] is None or info(t)[1] not in watched]
    return sorted(titles, key=lambda t: (info(t)[0] is not None, info(t)[0] or 0, screening_count(films[t])),
                  reverse=True)


def movie_view(title, cinemas, cached):
    rating, _, poster_url, _ = cached or [None, None, None, None]
    times = sorted(s["time"] for screenings in cinemas.values() for s in screenings)
    return {
        "title": title,
        "rating": round(rating, 1) if rating is not None else None,
        "poster_url": poster_url,
        "next_time": times[0] if times else "",
        "cinemas": [{"cinema": cinema, "screenings": screenings}
                    for cinema, screenings in sorted(cinemas.items(), key=lambda kv: kv[1][0]["time"])],
    }


def reuse_previous(previous, now):
    """Last good screen, if it still shows today's or tomorrow's programme."""
    movies = previous.get("movies")
    if not movies or previous.get("date") not in (now.date().isoformat(), (now.date() + timedelta(days=1)).isoformat()):
        return None
    return {key: previous.get(key) for key in ("city", "day", "date", "updated_at", "movies")}


# ---------------------------------------------------------------------------
# Saved State
# ---------------------------------------------------------------------------

def load_cache(state):
    if state.get("v") != STATE_VERSION:
        return {}
    return {title: entry for title, entry in (state.get("films") or {}).items()
            if isinstance(entry, list) and len(entry) == 4}


def build_state(cache, programme, top):
    """Cache of the current programme, trimmed to fit into Saved State."""
    films = {title: list(entry) for title, entry in cache.items() if title in programme}

    def size():
        return len(json.dumps({"v": STATE_VERSION, "films": films}, separators=(",", ":")))

    if size() > STATE_LIMIT_BYTES:
        for title, entry in films.items():
            if title not in top:
                entry[2] = None
    # Still too big: forget the lowest-rated films first, they'd be looked up again next time
    for title in sorted((t for t in films if t not in top), key=lambda t: films[t][0] or 0):
        if size() <= STATE_LIMIT_BYTES:
            break
        del films[title]
    return {"v": STATE_VERSION, "films": films}
