import requests

def post_to_webhook(payload: dict, webhook_url: str) -> requests.Response:
    try:
        headers = {"Content-Type": "application/json"}  # Add the required header
        print(f"Sending payload to webhook: {webhook_url}")
        resp = requests.post(webhook_url, json={"merge_variables": payload}, headers=headers, timeout=30)  # Wrap payload in "merge_variables"
        resp.raise_for_status()
        print(f"Webhook responded with {resp.status_code}")
        return resp
    except requests.RequestException as err:
        print(f"Failed to send to webhook: {err}")
        raise