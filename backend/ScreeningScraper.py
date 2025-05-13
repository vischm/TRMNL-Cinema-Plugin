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
            title, tags = extract_title_and_tags(movie_section)

            screenings = []
            for s in movie_section.find_all('span', class_='cinde-tag'):
                screenings.append({'time': s.get_text(strip=True), 'tags': tags})

            if not title or not screenings:
                continue

            if title not in movie_data:
                movie_data[title] = []

            # Append the cinema and screenings to the movie data
            if not any(cinema['cinema'] == cinema_name for cinema in movie_data[title]):
                movie_data[title].append({
                    'cinema': cinema_name,
                    'screenings': screenings
                })
            else:
                # Find the existing cinema entry and append screenings
                for cinema in movie_data[title]:
                    if cinema['cinema'] == cinema_name:
                        cinema['screenings'].extend(screenings)
                        break

    return movie_data


def extract_title_and_tags(movie_section):
    title_with_tags = movie_section.find('div', class_='movie').get_text(strip=True)
    if not title_with_tags:
        return None, None
    
    possible_tags = ["3D", "(OmU)", "(OF)"]
    title = title_with_tags
    tags = []
    for tag in possible_tags:
        if tag in title_with_tags:
            tag_without_parentheses = tag.replace('(', '').replace(')', '')
            if tag_without_parentheses == "OF":
                tag_without_parentheses = "OV" # More common abbreviation
            tags.append(tag_without_parentheses)
            title = title.replace(tag, '').strip()

    return title, tags


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