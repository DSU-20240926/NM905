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

mountains = [
    ('1', '지리산'),
    ('1', '북한산'),
    ('1', '설악산'),
    ('1', '팔공산'),
    ('1', '한라산'),
    ('1', '무등산'),
    ('1', '계룡산'),
    ('2', '금정산'),
    ('2', '가지산'),
    ('2', '남한산성'),
]

for park_cd, m_name in mountains:
    params = {
        'key': config.MOUNTAIN_API_KEY,
        'searchId': '07',
        'SCH_CD': 'MOBILE',
        'PARK_CD': park_cd,
        'QUERY': m_name,
        'type': 'json'
    }
    try:
        r = requests.get(config.MOUNTAIN_API_ENDPOINT, params=params, headers=headers, timeout=5)
        data = r.json()
        items = data.get('RESULT', [])
        print(f"[{park_cd}] {m_name}: {len(items)} items found. Code: {data.get('RESULT_CODE')}")
        if items:
            sample = items[0]
            print(f"   Sample: {sample.get('RDS_TRS_ADR')} | {sample.get('SERVICE_NAME')} | {sample.get('FRQ_HZ')}Hz | {sample.get('ARW_PWR_WTT')}W | lat={sample.get('LAT')}, lon={sample.get('LON')}")
    except Exception as e:
        print(f"[{park_cd}] {m_name}: error {e}")
