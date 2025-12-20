from ScreeningScraper import scrape_screenings
from ScreeningDataCleanup import clean_screening_data
from PostToWebhook import post_to_webhook

import json
import os

if __name__ == "__main__":
    with open('backend/config.json', 'r') as f:
        config = json.load(f)

    webhook_url = os.environ.get("TRMNL_WEBHOOK_URL")
    if not webhook_url:
        print("Webhook URL not set in environment variables.")
        exit(1)

    data = scrape_screenings(config["city"])
    json_data = clean_screening_data(data, config["cityDisplayName"])

    post_to_webhook(json_data, webhook_url)



def save_to_file(data: dict, filename: str) -> None:
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Data written to {filename}")
    except IOError as e:
        print(f"Failed to write data: {e}")