import requests
from bs4 import BeautifulSoup
import json


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://www.cinema.de/kino/kinoprogramm"


def scrape_screenings(city: str) -> dict:
    url = f"{BASE_URL}/{city}"
    print(f"Fetching data from: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    movie_data = {}

    cinemas = soup.find_all('div', class_='theater-wrapper')
    print(f"Found {len(cinemas)} cinemas.")

    for cinema in cinemas:
        cinema_name = cinema.find('a', class_='heading-he').get_text(strip=True)
        if not cinema_name:
            continue

        movie_sections = cinema.find_all('div', class_='screenings-by-theater')

        for movie_section in movie_sections:
            title_tag = movie_section.find('div', class_='movie')
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            screenings = [s.get_text(strip=True) for s in movie_section.find_all('span', class_='cinde-tag')]

            if not title or not screenings:
                continue

            if title not in movie_data:
                movie_data[title] = []

            movie_data[title].append({
                'cinema': cinema_name,
                'screenings': screenings
            })

    return movie_data


def save_to_file(data: dict, filename: str):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data written to {filename}")
    except IOError as e:
        print(f"Failed to write data: {e}")


if __name__ == "__main__":
    city = "leipzig"
    data = scrape_screenings(city)
    if data:
        save_to_file(data, 'out/screenings.json')