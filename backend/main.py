from ScreeningScraper import scrape_screenings
from RecentlyWatchedMoviesScraper import fetch_recent_watches
from ScreeningDataCleanup import clean_screening_data
from PostToWebhook import post_to_webhook

import json
import os

def print_selected_movies(data: dict) -> None:
    print("Found the following Movies:")
    for movie in data.get("movies", []):
        print(movie.get("title", "Unknown Title"))

if __name__ == "__main__":
    with open('backend/config.json', 'r') as f:
        config = json.load(f)

    webhook_url = os.environ.get("TRMNL_WEBHOOK_URL")
    if not webhook_url:
        print("Webhook URL not set in environment variables.")
        exit(1)

    data = scrape_screenings(config["city"]["name"])
    recently_watched_tmdb_ids = []
    if config["recentlyWatchedMovies"]["excludeWatchedMovies"]:
        recently_watched_tmdb_ids = fetch_recent_watches(
            config["recentlyWatchedMovies"]["letterboxdUsername"],
            config["recentlyWatchedMovies"]["numberOfDaysForRecentWatches"]
        )
    json_data = clean_screening_data(data, config["city"]["displayName"], recently_watched_tmdb_ids)

    post_to_webhook(json_data, webhook_url)
    
    print_selected_movies(json_data)

def save_to_file(data: dict, filename: str) -> None:
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data written to {filename}")
    except IOError as e:
        print(f"Failed to write data: {e}")