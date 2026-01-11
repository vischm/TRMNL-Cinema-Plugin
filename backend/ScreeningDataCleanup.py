from dataclasses import asdict
from LetterboxdAPIClient import get_movie_data

MOVIES_TO_IGNORE = ["Sneak Preview", "CineSneak", "Sonderveranstaltung", "Dokumentarfilm(e)", "Shorts Attack - Kurzfilme", "Sondervorstellung"]

def clean_screening_data(screening_data, city_display_name, recently_watched_tmdb_ids) -> str:
    # Create json structure that is expected by the frontend
    screening_json = {
        "movies": [],
        "city": city_display_name
    }
    for movie_title, screenings in screening_data.items():
        if movie_title not in MOVIES_TO_IGNORE:
            screening_json['movies'].append({
                "title": movie_title,
                "cinemas": screenings
            })

    # Get rating and poster for each movie
    for movie in screening_json['movies']:
        movie_data = get_movie_data(movie['title'])
        if movie_data is not None:
            movie.update(asdict(movie_data))
            
    # Remove recently watched movies
    screening_json['movies'] = [
        movie for movie in screening_json['movies']
        if movie.get('tmdb_id') not in recently_watched_tmdb_ids
    ]

    # Sort screening json by rating
    screening_json["movies"].sort(key=lambda x: x.get('rating') or 0, reverse=True)

    # Choose top 3 movies
    screening_json["movies"] = screening_json["movies"][:3]

    # Round rating when present
    for movie in screening_json['movies']:
        if movie.get('rating') is not None:
            movie['rating'] = round(movie['rating'], 1)

    return  screening_json