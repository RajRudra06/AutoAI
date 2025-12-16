import requests

AGENT_ID = "agent_001"
API_KEY = "secret_key_001"

HEADERS = {
    "X-AGENT-ID": AGENT_ID,
    "X-API-KEY": API_KEY,
}

def post(url: str, json: dict, timeout: int = 5):
    return requests.post(
        url,
        json=json,
        headers=HEADERS,
        timeout=timeout
    )

def get(url: str, timeout: int = 5):
    return requests.get(url, headers=HEADERS, timeout=timeout)