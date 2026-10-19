import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import requests
import config

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*'
}

candidate_parks = [
    # (park_cd, name)
    ('1', '지리산'), ('1', '설악산'), ('1', '북한산'), ('1', '계룡산'), ('1', '한려해상'),
    ('1', '속리산'), ('1', '내장산'), ('1', '가야산'), ('1', '덕유산'), ('1', '주왕산'),
    ('1', '태안해안'), ('1', '다도해해상'), ('1', '치악산'), ('1', '월악산'), ('1', '소백산'),
    ('1', '변산반도'), ('1', '월출산'), ('1', '경주'), ('1', '한라산'), ('1', '무등산'),
    ('1', '태백산'), ('1', '오대산'),
    ('2', '금정산'), ('2', '가지산'), ('2', '남한산성'), ('2', '대둔산'), ('2', '마이산'),
    ('2', '모악산'), ('2', '선운산'), ('2', '조계산'), ('2', '두륜산'), ('2', '금오산'),
    ('2', '문경새재'), ('2', '팔공산'), ('2', '연인산'), ('2', '수리산'),
    ('3', '장산'), ('3', '백양산'), ('3', '봉래산'), ('3', '황령산')
]

found = {}
for cd, name in candidate_parks:
    try:
        r = requests.get(config.MOUNTAIN_API_ENDPOINT, params={
            'key': config.MOUNTAIN_API_KEY,
            'searchId': '07',
            'SCH_CD': 'MOBILE',
            'PARK_CD': cd,
            'QUERY': name,
            'type': 'json',
            'pSize': 5
        }, headers=headers, timeout=5)
        d = r.json()
        items = d.get('RESULT', [])
        if items:
            found[name] = (cd, len(items), items[0].get('LAT'), items[0].get('LON'), items[0].get('RDS_TRS_ADR'))
    except Exception as e:
        pass

print(f"Total found parks: {len(found)}")
for k, v in found.items():
    print(f"  {k} ({v[0]}): count={v[1]}, lat={v[2]}, lon={v[3]}, adr={v[4]}")
