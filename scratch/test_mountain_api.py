import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import requests
import json
import config

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

# Try QUERY=지리산
params = {
    'key': config.MOUNTAIN_API_KEY,
    'searchId': '07',
    'SCH_CD': 'MOBILE',
    'PARK_CD': '1',
    'QUERY': '지리산',
    'type': 'json'
}

url = config.MOUNTAIN_API_ENDPOINT
print("Testing with QUERY=지리산...")
try:
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    print("Status code:", resp.status_code)
    print("Response text:", resp.text[:500])
except Exception as e:
    print("Error:", e)
