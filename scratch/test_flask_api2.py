import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import app
import json

client = app.app.test_client()
resp = client.get('/api/data?region=busan')
res = json.loads(resp.data.decode('utf-8'))
d = res.get('data', {})
print("mountain_station_count:", d.get('mountain_station_count'))
print("stations_by_provider:", d.get('stations_by_provider'))
print("stations_by_generation:", d.get('stations_by_generation'))
print("m_stations count in payload:", len(d.get('mountain_stations', [])))
if d.get('mountain_stations'):
    s = d['mountain_stations'][0]
    print("Sample station:", s['name'], s['provider_name'], s['generation'], "closest_stop:", s.get('closest_stop_name'), s.get('closest_stop_dist'), "m")
if d.get('top10'):
    t = d['top10'][0]
    print("Sample top10 stop closest station:", t.get('closest_station_name'), t.get('closest_station_dist'), "m", t.get('closest_station_prov'), t.get('closest_station_gen'))
