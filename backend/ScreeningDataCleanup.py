from ScreeningScraper import scrape_screenings
import json

def clean_screening_data(screening_data) -> str:
    # Choose three movies
    selected_movies = list(screening_data.keys())[:3]

    # Create json structure that is expected by the frontend
    screening_json = {
        "movies": []
    }
    for movie in selected_movies:
        screening_json["movies"].append({
            "title": movie,
            "cinemas": screening_data[movie]
        })

    return  screening_json


def save_to_file(data: dict, filename: str) -> None:
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data written to {filename}")
    except IOError as e:
        print(f"Failed to write data: {e}")


if __name__ == "__main__":
    city = "leipzig"
    data = scrape_screenings(city)
    json_data = clean_screening_data(data)

    if data:
        save_to_file(json_data, 'out/screenings.json')