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

for cus in ['SK', 'KT', 'LG']:
    r = requests.get(config.MOUNTAIN_API_ENDPOINT, params={
        'key': config.MOUNTAIN_API_KEY,
        'searchId': '07',
        'SCH_CD': 'MOBILE',
        'PARK_CD': '1',
        'QUERY': '북한산',
        'CUS_CD': cus,
        'type': 'json',
        'pSize': 5
    }, headers=headers, timeout=10)
    data = r.json()
    items = data.get('RESULT', [])
    print(f"CUS_CD={cus}: {len(items)} items")

for svc in ['5G', '4G', '3G']:
    r = requests.get(config.MOUNTAIN_API_ENDPOINT, params={
        'key': config.MOUNTAIN_API_KEY,
        'searchId': '07',
        'SCH_CD': 'MOBILE',
        'PARK_CD': '1',
        'QUERY': '북한산',
        'SERVICE_CD': svc,
        'type': 'json',
        'pSize': 5
    }, headers=headers, timeout=10)
    data = r.json()
    items = data.get('RESULT', [])
    print(f"SERVICE_CD={svc}: {len(items)} items")
