import json
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup


# Constants
HEADERS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.cinema.de/kino/kinoprogramm"
POSSIBLE_TAGS = ["3D", "(OmU)", "(OF)"]
TAG_REPLACEMENT_MAP = {"OF": "OV"} # Replace some tags with more common abbreviations


def scrape_screenings(city: str) -> dict:
    url = f"{BASE_URL}/{city}"
    
    html_content = fetch_html(url)
    if html_content is None:
        print("Failed to fetch HTML content.")
        return {}
    
    movie_data = {}

    cinemas = html_content.find_all('div', class_='theater-wrapper')
    for cinema in cinemas:
        cinema_name = cinema.find('a', class_='heading-he').get_text(strip=True)
        if not cinema_name:
            continue

        movie_sections = cinema.find_all('div', class_='screenings-by-theater')

        for movie_section in movie_sections:
            raw_title = movie_section.find("div", class_="movie").get_text(strip=True)
            title, tags = parse_title_and_tags(raw_title)
            screenings = extract_screenings(movie_section, tags)

            add_screenings_to_movie_data(movie_data, title, cinema_name, screenings)

    return movie_data

def fetch_html(url: str) -> BeautifulSoup:
    print(f"Fetching data from: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None 


def parse_title_and_tags(raw_title: str) -> Tuple[str, List[str]]:
    tags: List[str] = []
    title = raw_title

    for possible_tag in POSSIBLE_TAGS:
        if possible_tag in raw_title:
            clean_tag = possible_tag.strip("()")
            clean_tag = TAG_REPLACEMENT_MAP.get(clean_tag, clean_tag)
            tags.append(clean_tag)
            title = title.replace(possible_tag, "").strip()

    return title, tags


def extract_screenings(screening_section: BeautifulSoup, tags: List[str]) -> List[Dict[str, str]]:
    return [
        {"time": span.get_text(strip=True), "tags": tags}
        for span in screening_section.find_all("span", class_="cinde-tag")
    ]

def add_screenings_to_movie_data(movie_data, movie_title, cinema_name, screenings):
    if not movie_title or not screenings:
        return

    # Initialize list for this movie
    movie_data.setdefault(movie_title, [])

    # Find existing cinema entry
    existing = next((item for item in movie_data[movie_title] if item["cinema"] == cinema_name), None)
    if existing:
        existing["screenings"].extend(screenings)
    else:
        movie_data[movie_title].append({"cinema": cinema_name, "screenings": screenings})