"""Offline tests for src/transform.py. Run with: python -m unittest discover -s tests"""
import gzip
import json
import sys
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import transform  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LEIPZIG_HTML = gzip.decompress((FIXTURES / "cinema_leipzig.html.gz").read_bytes()).decode("utf-8")
FIXTURE_DAY = datetime(2026, 10, 19, 10, 0)  # the fixture is the programme of this day

RATINGS = {"Sinn und Sinnlichkeit": 4.04, "Whalefall": 4.2, "Digger": 3.91, "Street Fighter": 3.0}


def rss(*items):
    entries = "".join(
        "<item><title>x</title>%s%s</item>" % (
            "<letterboxd:watchedDate>%s</letterboxd:watchedDate>" % watched if watched else "",
            "<tmdb:%s>%s</tmdb:%s>" % (kind, tmdb_id, kind))
        for watched, kind, tmdb_id in items)
    return ('<?xml version="1.0" encoding="utf-8"?><rss xmlns:letterboxd="https://letterboxd.com" '
            'xmlns:tmdb="https://themoviedb.org"><channel>%s</channel></rss>' % entries).encode("utf-8")


class FakeResponse:
    def __init__(self, status_code=200, text="", payload=None, content=None):
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("status %s" % self.status_code)


def tmdb_id(title):
    return sum(map(ord, title))


class FakeWeb:
    """Stands in for transform.http_get: cinema.de from the fixture, Letterboxd from RATINGS."""

    def __init__(self, cinema_status=200, letterboxd_up=True, watched_rss=None):
        self.cinema_status = cinema_status
        self.letterboxd_up = letterboxd_up
        self.watched_rss = watched_rss
        self.calls = []

    def __call__(self, url, params=None):
        self.calls.append((url, params))
        if url.startswith("https://www.cinema.de/"):
            return FakeResponse(self.cinema_status, LEIPZIG_HTML if self.cinema_status == 200 else "not found")
        if url == transform.LETTERBOXD_SEARCH_URL:
            if not self.letterboxd_up:
                raise requests.ConnectionError("down")
            title = params["input"]
            film = {"name": title, "releaseYear": 2026, "rating": RATINGS.get(title, 2.5),
                    "poster": {"sizes": [{"url": "https://posters.test/%d.jpg" % tmdb_id(title)}]},
                    "links": [{"type": "tmdb", "id": str(tmdb_id(title))}]}
            return FakeResponse(payload={"items": [{"score": 1.0, "film": film}]})
        if url.endswith("/rss/"):
            return FakeResponse(content=self.watched_rss or rss())
        raise AssertionError("unexpected request to %s" % url)

    def searches(self):
        return [params["input"] for url, params in self.calls if url == transform.LETTERBOXD_SEARCH_URL]


def run_plugin(web, fields=None, state=None, previous=None, now=FIXTURE_DAY):
    input = {"trmnl": {"plugin_settings": {"custom_fields_values": {"city": "Leipzig", **(fields or {})}},
                       "state": state or {}, "previous_merge_variables": previous or {}}}
    with mock.patch.object(transform, "http_get", web), mock.patch.object(transform, "german_now", lambda: now):
        return transform.run(input)


class GermanNowTest(unittest.TestCase):
    def test_winter_and_summer_offsets(self):
        self.assertEqual(transform.german_now(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)), datetime(2026, 1, 15, 13, 0))
        self.assertEqual(transform.german_now(datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)), datetime(2026, 7, 15, 14, 0))

    def test_switches_at_one_o_clock_utc_on_the_last_sundays(self):
        # 2026: summer time from Sunday 29 March to Sunday 25 October
        self.assertEqual(transform.german_now(datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc)), datetime(2026, 3, 29, 1, 59))
        self.assertEqual(transform.german_now(datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc)), datetime(2026, 3, 29, 3, 0))
        self.assertEqual(transform.german_now(datetime(2026, 10, 25, 0, 59, tzinfo=timezone.utc)), datetime(2026, 10, 25, 2, 59))
        self.assertEqual(transform.german_now(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)), datetime(2026, 10, 25, 2, 0))


class InputTest(unittest.TestCase):
    def test_city_slug(self):
        cases = {
            "Leipzig": "leipzig", "  München ": "muenchen", "Köln": "koeln", "Frankfurt am Main": "frankfurt-am-main",
            "Halle (Saale)": "halle-saale", "Gießen": "giessen", "": "",
            "https://www.cinema.de/kino/kinoprogramm/freiburg-im-breisgau": "freiburg-im-breisgau",
        }
        for city, slug in cases.items():
            self.assertEqual(transform.city_slug(city), slug, city)

    def test_letterboxd_username(self):
        for value in ("someone", "@someone", "https://letterboxd.com/someone/", " someone "):
            self.assertEqual(transform.letterboxd_username(value), "someone", value)


class TitleTagsTest(unittest.TestCase):
    def test_tags_are_split_off_and_normalised(self):
        cases = {
            "Sinn und Sinnlichkeit (OmU)": ("Sinn und Sinnlichkeit", ["OmU"]),
            "Street Fighter (OF)": ("Street Fighter", ["OV"]),
            "Avatar (HFR 3D) (Deutsch/HFR 3D)": ("Avatar", ["HFR", "3D"]),
            "Die Odyssee (Deutsch/MXP 2D)": ("Die Odyssee", ["MXP"]),
            "Die Odyssee (OV/70 mm)": ("Die Odyssee", ["OV", "70mm"]),
            "Zoomania 2 3D": ("Zoomania 2", ["3D"]),
            "Der König der Löwen (deutsche Dialoge, englische Songs)": ("Der König der Löwen", []),
            "Film (Türkische Sprachfassung)": ("Film", ["TUR"]),
            "Annabelle (The Doll)": ("Annabelle (The Doll)", []),
            "Plain Title": ("Plain Title", []),
        }
        for raw, expected in cases.items():
            self.assertEqual(transform.split_title_tags(raw), expected, raw)


class ParseProgrammeTest(unittest.TestCase):
    def setUp(self):
        self.city, self.cinema_count, self.films = transform.parse_programme(LEIPZIG_HTML)

    def test_city_and_cinemas(self):
        self.assertEqual(self.city, "Leipzig")
        self.assertEqual(self.cinema_count, 8)
        self.assertEqual(len(self.films), 39)

    def test_screenings_are_merged_tagged_and_sorted(self):
        street_fighter = self.films["Street Fighter"]
        self.assertEqual(street_fighter["CineStar - Der Filmpalast"],
                         [{"time": "16:15", "tags": []}, {"time": "19:30", "tags": ["OV"]}])
        for cinemas in self.films.values():
            for screenings in cinemas.values():
                times = [s["time"] for s in screenings]
                self.assertEqual(times, sorted(times))

    def test_tags_and_ignored_titles_are_gone_from_titles(self):
        self.assertFalse([t for t in self.films if t.endswith(")") and "(" in t and "OmU" in t])
        self.assertFalse(set(self.films) & transform.MOVIES_TO_IGNORE)

    def test_empty_page(self):
        self.assertEqual(transform.parse_programme("<html><title>Seite nicht gefunden</title></html>"), ("", 0, {}))


class FilterTest(unittest.TestCase):
    films = {
        "A": {"Schauburg": [{"time": "14:00", "tags": []}, {"time": "20:00", "tags": []}]},
        "B": {"Passage Kinos": [{"time": "15:00", "tags": []}]},
    }

    def test_only_upcoming(self):
        self.assertEqual(transform.only_upcoming(self.films, "16:00"),
                         {"A": {"Schauburg": [{"time": "20:00", "tags": []}]}})

    def test_only_cinemas_matches_parts_case_insensitively(self):
        self.assertEqual(list(transform.only_cinemas(self.films, ["passage"])), ["B"])
        self.assertEqual(transform.only_cinemas(self.films, []), self.films)


class LetterboxdTest(unittest.TestCase):
    def test_select_search_result_prefers_newest_strong_match(self):
        response = {"items": [
            {"score": 10, "film": {"name": "Remake", "releaseYear": 2026}},
            {"score": 9, "film": {"name": "Original", "releaseYear": 1995}},
            {"score": 1, "film": {"name": "Weak", "releaseYear": 2030}},
        ]}
        self.assertEqual(transform.select_search_result(response)["name"], "Remake")
        self.assertIsNone(transform.select_search_result({"items": []}))
        self.assertIsNone(transform.select_search_result({"items": [{"score": 3}]}))

    def test_extract_poster_url_picks_the_smallest_sharp_size(self):
        sizes = [{"width": w, "height": w * 3 // 2, "url": "poster-%d" % w} for w in (2000, 150, 460, 300)]
        self.assertEqual(transform.extract_poster_url({"poster": {"sizes": sizes}}), "poster-300")
        self.assertEqual(transform.extract_poster_url({"poster": {"sizes": sizes[1:2]}}), "poster-150")
        self.assertIsNone(transform.extract_poster_url({"poster": None}))
        self.assertIsNone(transform.extract_poster_url({}))

    def test_parse_recent_watches_ignores_tv_and_old_entries(self):
        feed = rss(("2026-10-01", "movieId", 101), ("2025-01-01", "movieId", 102),
                   ("2026-10-10", "tvId", 103), (None, "movieId", 104))
        self.assertEqual(transform.parse_recent_watches(feed, date(2026, 10, 19), 180), {101})


class ParallelTest(unittest.TestCase):
    def test_returns_at_the_deadline_without_waiting_for_slow_or_failing_calls(self):
        def call(item):
            if item == "failing":
                raise ValueError(item)
            time.sleep(2 if item == "slow" else 0)
            return item.upper()

        started = time.monotonic()
        results = transform.run_parallel(call, ["a", "slow", "failing", "b"], started + 0.3)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(results, {"a": "A", "b": "B"})

    def test_background_result(self):
        self.assertEqual(transform.Background(lambda: 42).result(time.monotonic() + 1), 42)
        with self.assertRaises(ZeroDivisionError):
            transform.Background(lambda: 1 / 0).result(time.monotonic() + 1)
        with self.assertRaises(TimeoutError):
            transform.Background(time.sleep, 2).result(time.monotonic() + 0.1)


class RankAndStateTest(unittest.TestCase):
    def test_rank_by_rating_then_screenings_and_hide_watched(self):
        films = {
            "Good": {"X": [{"time": "20:00", "tags": []}]},
            "Better": {"X": [{"time": "20:00", "tags": []}]},
            "Unrated busy": {"X": [{"time": "18:00", "tags": []}, {"time": "20:00", "tags": []}]},
            "Unrated quiet": {"X": [{"time": "20:00", "tags": []}]},
            "Watched": {"X": [{"time": "20:00", "tags": []}]},
        }
        cache = {"Good": [3.5, 1, None, 0], "Better": [4.0, 2, None, 0], "Watched": [4.9, 3, None, 0]}
        self.assertEqual(transform.rank(films, cache, watched={3}), ["Better", "Good", "Unrated busy", "Unrated quiet"])

    def test_state_drops_old_films_and_fits_the_limit(self):
        poster = "https://a.ltrbxd.com/resized/film-poster/1/2/3/123-some-long-film-slug-0-150-0-225-crop.jpg?v=abcdef"
        cache = {"Film %03d" % i: [i / 30, 1000 + i, poster, 739900] for i in range(120)}
        cache["Gone"] = [5.0, 1, poster, 739900]
        programme = set(cache) - {"Gone"}
        state = transform.build_state(cache, programme, top={"Film 000"})
        size = len(json.dumps(state, separators=(",", ":")))
        self.assertLessEqual(size, transform.STATE_LIMIT_BYTES)
        self.assertNotIn("Gone", state["films"])
        self.assertEqual(state["films"]["Film 000"][2], poster)  # the top keeps its poster
        self.assertIn("Film 119", state["films"])  # the best-rated films stay cached
        self.assertEqual(cache["Film 001"][2], poster)  # the input cache isn't modified


class RunTest(unittest.TestCase):
    def test_ranks_films_and_hides_watched(self):
        web = FakeWeb(watched_rss=rss(("2026-10-01", "movieId", tmdb_id("Whalefall"))))
        result = run_plugin(web, {"letterboxd_username": "someone"})
        self.assertEqual(result["error"], "")
        self.assertEqual((result["city"], result["day"], result["date"]), ("Leipzig", "today", "2026-10-19"))
        self.assertEqual([m["title"] for m in result["movies"]], ["Sinn und Sinnlichkeit", "Digger", "Street Fighter"])
        first = result["movies"][0]
        self.assertEqual((first["rating"], first["next_time"]), (4.0, "17:15"))
        self.assertEqual(first["poster_url"], "https://posters.test/%d.jpg" % tmdb_id("Sinn und Sinnlichkeit"))
        self.assertEqual([c["cinema"] for c in first["cinemas"]], ["Regina-Palast", "Passage Kinos"])

    def test_second_run_uses_the_cache(self):
        first = run_plugin(FakeWeb())
        web = FakeWeb()
        second = run_plugin(web, state=first["trmnl_state"])
        self.assertEqual(web.searches(), [])
        self.assertEqual(second["movies"], first["movies"])

    def test_old_cache_entries_are_looked_up_again(self):
        state = run_plugin(FakeWeb())["trmnl_state"]
        later = datetime(2026, 10, 19 + transform.CACHE_MAX_AGE_DAYS + 1, 10, 0)
        web = FakeWeb()
        run_plugin(web, state=state, now=later)
        self.assertTrue(web.searches())

    def test_shows_tomorrow_after_the_last_screening(self):
        web = FakeWeb()
        result = run_plugin(web, now=datetime(2026, 10, 19, 23, 30))
        self.assertEqual((result["day"], result["date"]), ("tomorrow", "2026-10-20"))
        self.assertEqual(web.calls[1][1], {"day": "2026-10-20"})
        self.assertTrue(result["movies"])

    def test_without_letterboxd_films_are_ranked_by_screenings(self):
        result = run_plugin(FakeWeb(letterboxd_up=False))
        self.assertEqual(result["error"], "")
        self.assertEqual(len(result["movies"]), 3)
        self.assertIsNone(result["movies"][0]["rating"])
        self.assertNotIn("Whalefall", [m["title"] for m in result["movies"]])  # only 3 screenings

    def test_slow_cinema_de_ends_the_run_at_the_deadline(self):
        def slow(url, params=None):
            time.sleep(2)
            raise requests.ConnectionError("too late")

        started = time.monotonic()
        with mock.patch.object(transform, "TIME_BUDGET_S", 0.3):
            result = run_plugin(slow)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(result["error"], "cinema.de is not reachable right now.")

    def test_reports_the_city_setting_it_received(self):
        self.assertEqual(run_plugin(FakeWeb(), {"city": "Leipzig"})["city_setting"], "Leipzig")
        self.assertEqual(run_plugin(FakeWeb(), {"city": ""})["city_setting"], "")

    def test_unknown_city(self):
        result = run_plugin(FakeWeb(cinema_status=404), {"city": "Gibtsnicht"})
        self.assertIn("no cinemas for 'gibtsnicht'", result["error"])
        self.assertEqual(result["movies"], [])

    def test_missing_city(self):
        result = run_plugin(FakeWeb(), {"city": ""})
        self.assertEqual(result["error"], "Set your city in the plugin settings.")

    def test_outage_keeps_previous_screen_and_state(self):
        previous = run_plugin(FakeWeb())
        state = previous.pop("trmnl_state")

        def offline(url, params=None):
            raise requests.ConnectionError("offline")

        result = run_plugin(offline, state=state, previous=previous, now=datetime(2026, 10, 19, 12, 0))
        self.assertEqual(result["error"], "cinema.de is not reachable right now.")
        self.assertEqual(result["movies"], previous["movies"])
        self.assertEqual(result["trmnl_state"], state)

    def test_never_raises(self):
        def broken(url, params=None):
            raise ValueError("boom")

        result = run_plugin(broken)
        self.assertEqual(result["error"], "Something went wrong: ValueError")


if __name__ == "__main__":
    unittest.main()
