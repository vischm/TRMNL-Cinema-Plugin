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