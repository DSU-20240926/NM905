import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import app
import json

client = app.app.test_client()
resp = client.get('/api/data?region=busan')
print("Status code:", resp.status_code)
data = json.loads(resp.data.decode('utf-8'))
print("Keys:", list(data.keys()))
print("mountain_station_count:", data.get('mountain_station_count'))
print("stations_by_provider:", data.get('stations_by_provider'))
print("stations_by_generation:", data.get('stations_by_generation'))
m_stations = data.get('mountain_stations', [])
print("Number of mountain stations returned:", len(m_stations))
if m_stations:
    sample = m_stations[0]
    print("Sample mountain station:", json.dumps(sample, ensure_ascii=False, indent=2))

# Also test /api/mountain-stations
resp2 = client.get('/api/mountain-stations?region=busan&provider=skt')
print("\n/api/mountain-stations status:", resp2.status_code)
data2 = json.loads(resp2.data.decode('utf-8'))
print("Filtered SKT count:", data2.get('count'))
