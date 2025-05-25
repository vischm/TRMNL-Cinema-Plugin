import requests
import time
import random

LETTERBOXD_URL = "https://api.letterboxd.com/api/v0/"
MOVIE_TITLE_REPLACE_MAP = [{" ": "+"}, {"&": "%26"}]

MAX_RETRIES = 7
MIN_DELAY = 2 # seconds
INITIAL_DELAY = 4 # seconds

def get_movie_rating_and_poster(movie_title: str) -> tuple:
    print("Checking Movie: " + movie_title)
    url = get_request_url(movie_title)

    delay = INITIAL_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=10)

            if r.status_code == 200:
                print("Letterboxd API is reachable.")
                search_result = select_search_result(r.json())
                if( not search_result):
                    print(f"No suitable search result found for '{movie_title}'.")
                    return None, None
                rating = extract_rating(search_result)
                poster = extract_poster_url(search_result)
                time.sleep(MIN_DELAY)
                return rating, poster

            elif r.status_code == 429:
                print(f"Rate limited (429). Retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                delay += random.uniform(0, 1)  # Add jitter
            else:
                print(f"Request failed with status {r.status_code}.")
                break

        except requests.RequestException as e:
            print(f"Request failed due to network error: {e}")
            time.sleep(delay)
            delay *= 2
            delay += random.uniform(0, 1)

    print("Exceeded maximum retries.")
    return None, None
    

def get_request_url(movie_title: str):
    movie_title_for_url = movie_title
    for replacement in MOVIE_TITLE_REPLACE_MAP:
        for old, new in replacement.items():
            movie_title_for_url = movie_title_for_url.replace(old, new)
    return f"{LETTERBOXD_URL}search?input=" + movie_title_for_url + "&include=FilmSearchItem"

def select_search_result(response: str) -> str:
    try:
        items = response.get('items', [])
        # Filter out all items with a 'score' smaller than half of the max score
        items = [item for item in items if item.get('score', 0) >= 0.5 * items[0].get('score', 0)]
        # Take up to the first 3 movies
        film_candidates = [item['film'] for item in items[:3] if 'film' in item]
        if not film_candidates:
            return None
        # Pick the film with the newest release year, as it is most likely the one in cinemas
        return max(
            film_candidates,
            key=lambda f: f.get('releaseYear', 0)
        )
    except Exception as e:
        print(f"Error parsing Letterboxd response: {e}")
        return None
    

def extract_rating(search_result: str) -> float:
    try:
        return search_result['rating']
    except KeyError:
        return None
    
    
def extract_poster_url(search_result: str) -> str:
    try:
        return search_result['poster']['sizes'][0]['url']
    except KeyError:
        return None
