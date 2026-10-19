import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import requests
import json
import config

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

r = requests.get(config.MOUNTAIN_API_ENDPOINT, params={
    'key': config.MOUNTAIN_API_KEY,
    'searchId': '07',
    'SCH_CD': 'MOBILE',
    'PARK_CD': '1',
    'QUERY': '북한산',
    'type': 'json',
    'pSize': 3
}, headers=headers, timeout=10)

data = r.json()
print("Keys in response:", data.keys())
print("Result Code:", data.get('RESULT_CODE'))
print("Sample item 0:", json.dumps(data.get('RESULT', [])[0], ensure_ascii=False, indent=2))
if len(data.get('RESULT', [])) > 1:
    print("Sample item 1:", json.dumps(data.get('RESULT', [])[1], ensure_ascii=False, indent=2))
