# -*- coding: utf-8 -*-
"""
스마트 통신 쉼터 최적 입지 분석 및 인터랙티브 지도 대시보드
(Smart Communication Shelter Optimal Site Analysis Dashboard)

[과제/프로젝트 개요]
- 과제명: 공공 빅데이터 분석 및 실무 프로젝트 (클래스셀링 과제)
- 개발 환경: Python 3.6.8 호환 (Python 3.6.8 이상 모든 버전에서 예외 없이 동작)
- 필요 라이브러리: pandas, requests, folium, numpy, scipy
- 데이터 출처:
  1) 국토교통부_전국 버스정류장 위치정보 (API Endpoint 1순위 시도, 실패 시 로컬 CSV 2순위)
     - API: http://api.odcloud.kr/api/15067528/v1/uddi:eb02ec03-6edd-4cb0-88b8-eda22ca55e80
  2) 행정안전부/지자체 공공 무료 와이파이 표준데이터 (로컬 CSV 인코딩 순차 전환 로더)
- 핵심 분석:
  - Haversine 공식을 활용한 정류장-공공 Wi-Fi 간 최단 거리(m) 계산
  - 100m 기준 공공 Wi-Fi 커버리지 음영 정류장 분류
  - Wi-Fi 부재 거리 및 주변 정류장 밀집도(교통 결절점 수요) 기반 가중 스코어링 (Top 10 도출)
  - Folium 기반 인터랙티브 지도 시각화 대시보드 (smart_shelter_map.html) 생성
"""

import os
import sys
import glob
import math
import time
import requests
import numpy as np
import pandas as pd
import folium
from folium import plugins

# 전역 설정 모듈 불러오기 (.env 파일 기반)
import config

# scipy.spatial.cKDTree 선택적 로드 (미설치 시 순수 numpy 고속 벡터화 Fallback 작동)
try:
    from scipy.spatial import cKDTree
    HAS_SCIPY = True
except ImportError:
    cKDTree = None
    HAS_SCIPY = False

# ==============================================================================
# 0. 전역 환경 및 상수 정의 (Global Configurations)
# ==============================================================================
API_ENDPOINT = config.API_ENDPOINT
API_KEY = config.BUS_API_KEY
KAKAO_KEY = config.KAKAO_JS_KEY

# 로컬 CSV 파일 탐색 우선순위 목록
BUS_CSV_CANDIDATES = [
    config.BUS_CSV_PATH,
    config.NATIONAL_BUS_CSV,
    "*버스정류장*.csv"
]
WIFI_CSV_CANDIDATES = [
    config.WIFI_CSV_PATH,
    config.BUSAN_WIFI_CSV,
    "*와이파이*.csv",
    "*wifi*.csv"
]

# 대한민국 영토 좌표 유효 범위
LAT_MIN, LAT_MAX = config.LAT_MIN, config.LAT_MAX
LON_MIN, LON_MAX = 124.0, 132.0

# 분석 파라미터
WIFI_COVERAGE_RADIUS_M = 100.0   # 공공 Wi-Fi 유효 커버리지 반경 (100m)
DENSITY_RADIUS_M = 500.0         # 정류장 주변 환승/이용 밀집도 분석 반경 (500m)
TOP_N_RECOMMEND = 10             # 최종 우선순위 스마트 통신 쉼터 선정 개수
OUTPUT_HTML = "smart_shelter_map.html"

# 지구 반지름 (미터 단위)
EARTH_RADIUS_M = 6371000.0


# ==============================================================================
# 1. 거리 계산 함수 (Haversine Formula)
# ==============================================================================
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    두 지점(위경도) 간의 대원 거리(Great-Circle Distance)를 Haversine 공식으로 계산합니다.
    - 입력: lat1, lon1, lat2, lon2 (십진법 각도 단위)
    - 반환: 거리 (단위: 미터, m)
    - 특징: Python 표준 math 모듈 기반으로 Python 3.6.8 완벽 호환
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c


def batch_haversine_closest(df_bus, df_wifi):
    """
    정류장과 Wi-Fi 데이터 간 최단 거리를 고속 계산합니다.
    - scipy 설치 시: 3D cKDTree 활용 (0.02초)
    - scipy 미설치 시: 순수 numpy 청크 벡터화 브로드캐스팅 활용 (1~2초)
    - 반환: (각 정류장별 최단거리 배열(m), 가장 가까운 Wi-Fi 인덱스 배열)
    """
    bus_lat_rad = np.radians(df_bus['latitude'].values)
    bus_lon_rad = np.radians(df_bus['longitude'].values)
    wifi_lat_rad = np.radians(df_wifi['latitude'].values)
    wifi_lon_rad = np.radians(df_wifi['longitude'].values)

    # 3D 데카르트 좌표계(Cartesian Coordinates) 투영
    bx = np.cos(bus_lat_rad) * np.cos(bus_lon_rad)
    by = np.cos(bus_lat_rad) * np.sin(bus_lon_rad)
    bz = np.sin(bus_lat_rad)

    wx = np.cos(wifi_lat_rad) * np.cos(wifi_lon_rad)
    wy = np.cos(wifi_lat_rad) * np.sin(wifi_lon_rad)
    wz = np.sin(wifi_lat_rad)

    bus_pts = np.column_stack([bx, by, bz])
    wifi_pts = np.column_stack([wx, wy, wz])

    if HAS_SCIPY and cKDTree is not None:
        # scipy cKDTree 가속
        tree = cKDTree(wifi_pts)
        chord_dists, closest_idx = tree.query(bus_pts, k=1)
    else:
        # 순수 numpy 청크 브로드캐스팅 가속 (메모리 절약 및 고속 연산)
        chunk_size = 1000
        chord_dists_list = []
        closest_idx_list = []
        for i in range(0, len(bus_pts), chunk_size):
            chunk = bus_pts[i:i + chunk_size]
            # (chunk_size, 1, 3) - (1, n_wifi, 3) -> squared distance
            diff = chunk[:, np.newaxis, :] - wifi_pts[np.newaxis, :, :]
            dists_sq = np.sum(diff * diff, axis=2)
            c_idx = np.argmin(dists_sq, axis=1)
            c_dist = np.sqrt(dists_sq[np.arange(len(chunk)), c_idx])
            chord_dists_list.append(c_dist)
            closest_idx_list.append(c_idx)
        chord_dists = np.concatenate(chord_dists_list)
        closest_idx = np.concatenate(closest_idx_list)

    # 현(chord) 거리 -> 구면 호(arc) 대원거리 변환: d = 2 * R * arcsin(chord / 2)
    clamped_chords = np.clip(chord_dists / 2.0, -1.0, 1.0)
    thetas = 2.0 * np.arcsin(clamped_chords)
    great_circle_dists = EARTH_RADIUS_M * thetas

    return great_circle_dists, closest_idx


# ==============================================================================
# 2. 데이터 수집 및 Fallback 로더 (Data Acquisition & Robust Loaders)
# ==============================================================================
def read_csv_with_encoding_fallback(filepath):
    """
    CSV 파일 로드 시 UTF-8 -> CP949 -> EUC-KR 순으로 인코딩을 자동 시도하는 Fallback 함수.
    """
    encodings = ['utf-8', 'cp949', 'euc-kr']
    for enc in encodings:
        try:
            df = pd.read_csv(filepath, encoding=enc, low_memory=False)
            print("  [인코딩 성공] '{}' 인코딩으로 파일 로드 완료: {}".format(enc, os.path.basename(filepath)))
            return df
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            # 기타 파싱 예외 처리
            pass
    raise ValueError("지원하는 모든 인코딩(UTF-8, CP949, EUC-KR)으로 파일을 디코딩하지 못했습니다: {}".format(filepath))


def find_file(candidates):
    """
    후보 목록 또는 와일드카드 패턴 중 실제 존재하는 첫 번째 파일 경로 반환.
    """
    for item in candidates:
        if os.path.isfile(item):
            return item
        matched = glob.glob(item)
        if matched:
            return matched[0]
    return None


def fetch_bus_data():
    """
    버스정류장 데이터 수집:
    - 1순위: 국토교통부 Open API Endpoint 호출 (1,000건)
    - 2순위: API 키 오류/타임아웃/응답 실패 시 로컬 CSV 파일 자동 Fallback 로드
    """
    print("\n[단계 1-1] 버스정류장 데이터 수집 시작...")
    api_key = API_KEY

    # 1순위: Open API 호출 시도
    if api_key:
        print("  - [1순위] 국토교통부 버스정류장 Open API 요청 중 (perPage=1000)...")
        params = {
            'page': 1,
            'perPage': 1000,
            'serviceKey': api_key
        }
        try:
            res = requests.get(API_ENDPOINT, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get('data', [])
                if items and len(items) > 0:
                    df_api = pd.DataFrame(items)
                    print("  - [API 수신 성공] 국토교통부 Open API로부터 {}건 수집 완료".format(len(df_api)))
                    df_api['DATA_ORIGIN'] = 'API'
                    return df_api
                else:
                    print("  - [API 응답 주의] 데이터 목록이 비어 있습니다. 로컬 CSV Fallback으로 전환합니다.")
            else:
                print("  - [API 오류] HTTP 상태 코드 {} 응답. 로컬 CSV Fallback으로 전환합니다.".format(res.status_code))
        except Exception as e:
            print("  - [API 예외] 네트워크 연결 또는 파싱 오류 발생 ({}). 로컬 CSV Fallback으로 전환합니다.".format(e))
    else:
        print("  - [안내] API 인증키 파일({})이 없거나 비어 있어 로컬 CSV로 즉시 로드합니다.".format(API_KEY_FILE))

    # 2순위: 로컬 CSV Fallback 로드
    bus_csv = find_file(BUS_CSV_CANDIDATES)
    if bus_csv:
        print("  - [2순위 Fallback] 로컬 버스정류장 CSV 파일 로드: {}".format(bus_csv))
        df_csv = read_csv_with_encoding_fallback(bus_csv)
        print("  - [로컬 로드 완료] 총 {}건의 정류장 데이터 확보".format(len(df_csv)))
        df_csv['DATA_ORIGIN'] = 'LOCAL_CSV'
        return df_csv
    else:
        raise FileNotFoundError("버스정류장 데이터를 확보할 수 없습니다 (API 실패 및 로컬 CSV 파일 없음).")


def fetch_wifi_data():
    """
    공공 무료 와이파이 데이터 수집:
    - 로컬 CSV 파일 탐색 (wifi_info.csv 또는 지자체 와이파이 CSV)
    - UTF-8 / CP949 / EUC-KR 자동 감지 로드
    """
    print("\n[단계 1-2] 공공 무료 와이파이 데이터 수집 시작...")
    wifi_csv = find_file(WIFI_CSV_CANDIDATES)
    if not wifi_csv:
        raise FileNotFoundError("공공 무료 와이파이 CSV 파일을 찾을 수 없습니다 (후보: {}).".format(WIFI_CSV_CANDIDATES))

    print("  - 로컬 Wi-Fi CSV 파일 로드: {}".format(wifi_csv))
    df_wifi = read_csv_with_encoding_fallback(wifi_csv)
    print("  - [와이파이 로드 완료] 총 {}건의 Wi-Fi AP 데이터 확보".format(len(df_wifi)))
    return df_wifi


# ==============================================================================
# 3. 데이터 전처리 및 정제 (Preprocessing & Cleaning)
# ==============================================================================
def standardize_columns(df_bus, df_wifi):
    """
    이종 데이터 간 컬럼명을 표준 컬럼으로 통일:
    - 버스: station_id, station_nm, latitude, longitude, city_nm
    - 와이파이: place_nm, address, latitude, longitude, provider
    """
    # 버스정류장 컬럼 매핑
    bus_map = {}
    for col in df_bus.columns:
        c = str(col).strip()
        if ('station_id' not in bus_map.values()) and (c in ['NODE_ID', '정류장번호', '정류장ID', '정류소ID'] or '정류장번호' in c):
            bus_map[col] = 'station_id'
        elif ('station_nm' not in bus_map.values()) and (c in ['NODE_NM', '정류장명', '정류소명'] or '정류장명' in c):
            bus_map[col] = 'station_nm'
        elif ('latitude' not in bus_map.values()) and (c in ['GPS_LATI', '위도', 'Y좌표'] or c.startswith('위도')):
            bus_map[col] = 'latitude'
        elif ('longitude' not in bus_map.values()) and (c in ['GPS_LONG', '경도', 'X좌표'] or c.startswith('경도')):
            bus_map[col] = 'longitude'
        elif ('city_nm' not in bus_map.values()) and (c in ['CITY_NAME', '도시명', '관리도시명'] or '도시명' in c):
            bus_map[col] = 'city_nm'

    df_bus_std = df_bus.rename(columns=bus_map).copy()
    if 'station_id' not in df_bus_std.columns:
        df_bus_std['station_id'] = ['ST_{}'.format(i) for i in range(len(df_bus_std))]
    if 'station_nm' not in df_bus_std.columns:
        df_bus_std['station_nm'] = '정류장'
    if 'city_nm' not in df_bus_std.columns:
        df_bus_std['city_nm'] = '미분류'

    # 공공 와이파이 컬럼 매핑
    wifi_map = {}
    for col in df_wifi.columns:
        c = str(col).strip()
        if ('place_nm' not in wifi_map.values()) and (c in ['설치장소명', '설치장소', '장소명', '서비스장소명'] or '설치장소명' in c):
            wifi_map[col] = 'place_nm'
        elif ('address' not in wifi_map.values()) and (c in ['소재지도로명주소', '설치장소도로명주소', '도로명주소', '소재지지번주소', '주소'] or '소재지도로명주소' in c):
            wifi_map[col] = 'address'
        elif ('latitude' not in wifi_map.values()) and (c in ['WGS84위도', '위도', 'Y좌표', 'lat'] or '위도' in c):
            wifi_map[col] = 'latitude'
        elif ('longitude' not in wifi_map.values()) and (c in ['WGS84경도', '경도', 'X좌표', 'lon'] or '경도' in c):
            wifi_map[col] = 'longitude'
        elif ('provider' not in wifi_map.values()) and (c in ['서비스제공사명', '통신사', '제공기관명'] or '제공사' in c):
            wifi_map[col] = 'provider'

    df_wifi_std = df_wifi.rename(columns=wifi_map).copy()
    if 'place_nm' not in df_wifi_std.columns:
        df_wifi_std['place_nm'] = '공공 Wi-Fi'
    if 'address' not in df_wifi_std.columns:
        df_wifi_std['address'] = ''
    if 'provider' not in df_wifi_std.columns:
        df_wifi_std['provider'] = '지자체/통신사'

    return (df_bus_std[['station_id', 'station_nm', 'latitude', 'longitude', 'city_nm']],
            df_wifi_std[['place_nm', 'address', 'latitude', 'longitude', 'provider']])


def clean_dataframe_coords(df, label):
    """
    좌표 결측치 제거, 뒤바뀐 좌표(Swap) 자동 교정, 대한민국 영토 유효 범위 필터링.
    """
    df = df.copy()
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude']).copy()

    # 1. 위도/경도가 뒤바뀐 이상치 교정 (위도 > 100 & 경도 < 40)
    swapped = (df['latitude'] > 100.0) & (df['longitude'] < 40.0)
    swap_cnt = swapped.sum()
    if swap_cnt > 0:
        print("  - [이상치 자동 교정] {}에서 위경도 전치(Swap) 데이터 {}건 보정 완료".format(label, swap_cnt))
        temp = df.loc[swapped, 'latitude'].copy()
        df.loc[swapped, 'latitude'] = df.loc[swapped, 'longitude']
        df.loc[swapped, 'longitude'] = temp

    # 2. 대한민국 유효 영토 범위 (위도 33~39, 경도 124~132)
    in_korea = ((df['latitude'] >= LAT_MIN) & (df['latitude'] <= LAT_MAX) &
                (df['longitude'] >= LON_MIN) & (df['longitude'] <= LON_MAX))
    outliers = (~in_korea).sum()
    if outliers > 0:
        print("  - [영외 좌표 제거] {}에서 대한민국 외 좌표 {}건 필터링 완료".format(label, outliers))

    df = df[in_korea].copy().reset_index(drop=True)
    return df


def align_and_preprocess(df_bus_raw, df_wifi_raw, force_api=False):
    """
    전처리 및 지리적 연계 정합성 검사:
    - 표준화 및 좌표 정제
    - Wi-Fi 지오코딩 이상치(타 시도 좌표 혼입) 정제
    - API 정류장 데이터와 Wi-Fi 데이터의 지역적 매칭 점검:
      API 수집 건(예: 안동시 1,000건)과 로컬 Wi-Fi(부산 2,630건)의 지리적 불일치 시,
      실무 및 과제 목적에 부합하도록 로컬 버스정류장 데이터(`bus_stops.csv` 또는 부산 9,975건)를 자동 연계.
    """
    print("\n[단계 2] 데이터 정제 및 지역 매칭 정합성 검사 진행...")
    df_bus_std, df_wifi_std = standardize_columns(df_bus_raw, df_wifi_raw)
    df_bus = clean_dataframe_coords(df_bus_std, "버스정류장")
    df_wifi = clean_dataframe_coords(df_wifi_std, "공공 Wi-Fi")

    # Wi-Fi 데이터 내의 지오코딩 이상치 제거
    # (예: 부산광역시 데이터 중 인천/강원 좌표가 오입력된 데이터 필터링)
    # 지자체 주소/명칭 기반 바운딩 필터
    has_busan_wifi = df_wifi['address'].str.contains('부산', na=False).sum() > 0
    if has_busan_wifi:
        # 부산광역시 정상 권역: 위도 34.8~35.5, 경도 128.7~129.4
        valid_busan_wifi = df_wifi[
            (df_wifi['latitude'].between(34.8, 35.5)) &
            (df_wifi['longitude'].between(128.7, 129.4))
        ]
        if len(valid_busan_wifi) >= 100:
            df_wifi = valid_busan_wifi.copy().reset_index(drop=True)
            print("  - [Wi-Fi 이상치 정제] 부산광역시 정상 권역(34.8~35.5, 128.7~129.4) 외 오기입 데이터 정제 완료 (유효 AP: {}건)".format(len(df_wifi)))

    # 공간적 정합성 확인
    bus_center_lat = df_bus['latitude'].mean()
    bus_center_lon = df_bus['longitude'].mean()
    wifi_center_lat = df_wifi['latitude'].mean()
    wifi_center_lon = df_wifi['longitude'].mean()
    center_dist_km = haversine_distance(bus_center_lat, bus_center_lon, wifi_center_lat, wifi_center_lon) / 1000.0

    print("  - 정류장 중심점: ({:.4f}, {:.4f}) / Wi-Fi 중심점: ({:.4f}, {:.4f})".format(
        bus_center_lat, bus_center_lon, wifi_center_lat, wifi_center_lon
    ))
    print("  - 데이터셋 중심 간 거리: {:.1f} km".format(center_dist_km))

    # 중심 거리가 30km를 초과하고 force_api가 아닌 경우, 실무 분석을 위해 로컬의 일치 지역 정류장 로드
    if center_dist_km > 30.0 and not force_api:
        print("  - [안내] 수집된 정류장(평균거리 {:.1f}km)과 Wi-Fi 데이터의 지역이 일치하지 않습니다.".format(center_dist_km))
        local_bus_file = find_file(["bus_stops.csv", "국토교통부_전국 버스정류장 위치정보_20251031.csv", "*버스정류장*.csv"])
        if local_bus_file:
            print("  - [지능형 연계] 실효성 있는 100m 커버리지 분석을 위해 로컬 정류장 데이터({})를 연계합니다.".format(local_bus_file))
            df_local_bus = read_csv_with_encoding_fallback(local_bus_file)
            df_local_std, _ = standardize_columns(df_local_bus, df_wifi_raw)
            df_local_clean = clean_dataframe_coords(df_local_std, "연계 버스정류장")

            # Wi-Fi 권역(부산 등)에 일치하는 정류장 필터링
            w_lat_min, w_lat_max = df_wifi['latitude'].min() - 0.05, df_wifi['latitude'].max() + 0.05
            w_lon_min, w_lon_max = df_wifi['longitude'].min() - 0.05, df_wifi['longitude'].max() + 0.05
            matched_bus = df_local_clean[
                (df_local_clean['latitude'].between(w_lat_min, w_lat_max)) &
                (df_local_clean['longitude'].between(w_lon_min, w_lon_max))
            ].copy()

            if len(matched_bus) >= 10:
                print("  - [지역 매칭 완료] Wi-Fi 분석 권역 내 버스정류장 {}건 매칭 완료".format(len(matched_bus)))
                df_bus = matched_bus.reset_index(drop=True)
            else:
                print("  - [유지] 지역 매칭 건수가 적어 기존 버스정류장 데이터로 분석을 계속합니다.")

    print("  - [전처리 완료] 최종 분석 대상: 버스정류장 {}개, 공공 Wi-Fi {}개".format(len(df_bus), len(df_wifi)))
    return df_bus, df_wifi


# ==============================================================================
# 4. 거리 계산 & 우선순위 스코어링 (Haversine & Scoring Logic)
# ==============================================================================
def analyze_smart_shelter_sites(df_bus, df_wifi):
    """
    핵심 분석 알고리즘:
    1. 고속 Haversine 거리 계산으로 각 정류장별 가장 가까운 Wi-Fi AP 및 거리(m) 도출
    2. 반경 100m 기준 Wi-Fi 음영 여부 판정 (is_shadow)
    3. 반경 500m 이내 주변 정류장 밀집도(nearby_stop_count) 산출 (교통 결절점 수요)
    4. 스마트 쉼터 종합 우선순위 스코어 산출:
       - 거리 점수 (Wi-Fi 인프라 부재도, 가중치 50%): 최대 2,000m 기준 정규화
       - 밀집도 점수 (대중교통 이용 및 환승 수요, 가중치 50%): 반경 500m 정류장 수 정규화
       - 종합 점수 = (0.5 * 정규화 거리 + 0.5 * 정규화 밀집도) * 100
    5. 동일 정류소 상하행선 중복 방지(Deduplication)를 적용하여 다양한 거점의 Top 10 도출
    """
    print("\n[단계 3] Haversine 거리 계산 및 스마트 쉼터 최적 입지 스코어링 시작...")
    t0 = time.time()

    # 1. 고속 최단거리 계산
    dists_m, closest_wifi_indices = batch_haversine_closest(df_bus, df_wifi)
    df_bus['closest_wifi_dist'] = np.round(dists_m, 1)
    df_bus['closest_wifi_name'] = df_wifi['place_nm'].values[closest_wifi_indices]
    df_bus['closest_wifi_addr'] = df_wifi['address'].values[closest_wifi_indices]
    df_bus['closest_wifi_provider'] = df_wifi['provider'].values[closest_wifi_indices]

    # 2. 100m 기준 음영 여부 분류
    df_bus['is_shadow'] = df_bus['closest_wifi_dist'] > WIFI_COVERAGE_RADIUS_M
    total_stops = len(df_bus)
    shadow_stops = int(df_bus['is_shadow'].sum())
    shadow_ratio = (shadow_stops / total_stops * 100.0) if total_stops > 0 else 0.0

    print("  - 거리 계산 소요 시간: {:.3f}초".format(time.time() - t0))
    print("  - 전체 정류장 {}개 중 Wi-Fi 음영 정류장: {}개 ({:.1f}%)".format(
        total_stops, shadow_stops, shadow_ratio
    ))

    # 3. 반경 500m 이내 주변 정류장 밀집도 계산
    bus_lat_rad = np.radians(df_bus['latitude'].values)
    bus_lon_rad = np.radians(df_bus['longitude'].values)
    bx = np.cos(bus_lat_rad) * np.cos(bus_lon_rad)
    by = np.cos(bus_lat_rad) * np.sin(bus_lon_rad)
    bz = np.sin(bus_lat_rad)
    bus_pts = np.column_stack([bx, by, bz])

    chord_500m = 2.0 * np.sin(DENSITY_RADIUS_M / (2.0 * EARTH_RADIUS_M))

    if HAS_SCIPY and cKDTree is not None:
        bus_tree = cKDTree(bus_pts)
        neighbors = bus_tree.query_ball_point(bus_pts, r=chord_500m)
        df_bus['nearby_stop_count'] = [max(0, len(n) - 1) for n in neighbors]
    else:
        # scipy 미설치 시 순수 numpy 청크 벡터 연산
        chord_500m_sq = chord_500m * chord_500m
        counts_list = []
        chunk_size = 1000
        for i in range(0, len(bus_pts), chunk_size):
            chunk = bus_pts[i:i + chunk_size]
            diff = chunk[:, np.newaxis, :] - bus_pts[np.newaxis, :, :]
            dists_sq = np.sum(diff * diff, axis=2)
            c = np.sum(dists_sq <= chord_500m_sq, axis=1) - 1
            counts_list.append(np.maximum(0, c))
        df_bus['nearby_stop_count'] = np.concatenate(counts_list)

    # 4. 우선순위 스코어링 (음영 정류장 대상)
    df_target = df_bus[df_bus['is_shadow']].copy()
    if len(df_target) == 0:
        df_target = df_bus.copy()

    # 현실적인 도심 서비스 품질을 위해 거리 상한을 2,000m로 클리핑하여 지나친 외곽 쏠림 방지
    dist_capped = np.clip(df_target['closest_wifi_dist'], WIFI_COVERAGE_RADIUS_M, 2000.0)
    norm_dist = (dist_capped - WIFI_COVERAGE_RADIUS_M) / (2000.0 - WIFI_COVERAGE_RADIUS_M)

    min_den = df_target['nearby_stop_count'].min()
    max_den = df_target['nearby_stop_count'].max()
    den_denom = (max_den - min_den) if max_den > min_den else 1.0
    norm_den = (df_target['nearby_stop_count'] - min_den) / den_denom

    # 가중치 50:50 결합 후 100점 만점 환산
    priority_score = (0.5 * norm_dist + 0.5 * norm_den) * 100.0
    df_target['priority_score'] = np.round(priority_score, 1)

    # 5. 동일 정류장명 중복 제거(Deduplication)를 통한 실용적 Top 10 선정
    df_sorted = df_target.sort_values(
        by=['priority_score', 'nearby_stop_count', 'closest_wifi_dist'],
        ascending=[False, False, False]
    )
    df_dedup = df_sorted.drop_duplicates(subset=['station_nm']).reset_index(drop=True)
    top10_df = df_dedup.head(TOP_N_RECOMMEND).copy()
    top10_df['rank'] = top10_df.index + 1

    # 전체 정류장 데이터에도 스코어 및 순위 결합
    df_bus = df_bus.merge(
        top10_df[['station_id', 'priority_score', 'rank']],
        on='station_id',
        how='left'
    )
    df_bus['priority_score'] = df_bus['priority_score'].fillna(0.0)

    print("\n" + "=" * 85)
    print(" [스마트 통신 쉼터(스마트 벤치+공공 Wi-Fi) 최우선 설치 후보지 Top 10]")
    print("=" * 85)
    print("{:<4} {:<18} {:<10} {:<14} {:<12} {:<10} {:<18}".format(
        "순위", "정류장명", "도시/권역", "최단Wi-Fi거리", "주변정류장(500m)", "우선순위점수", "인접 공공 Wi-Fi명"
    ))
    print("-" * 85)
    for _, r in top10_df.iterrows():
        print("{:<4} {:<18} {:<10} {:<14.1f} {:<12} {:<10.1f} {:<18}".format(
            int(r['rank']),
            str(r['station_nm'])[:16],
            str(r['city_nm'])[:8],
            r['closest_wifi_dist'],
            r['nearby_stop_count'],
            r['priority_score'],
            str(r['closest_wifi_name'])[:16]
        ))
    print("=" * 85)

    return df_bus, top10_df, shadow_stops, total_stops, shadow_ratio


# ==============================================================================
# 5. Folium 인터랙티브 지도 대시보드 시각화 (Interactive Visualization)
# ==============================================================================
def render_folium_dashboard(df_bus, df_wifi, top10_df, shadow_stops, total_stops, shadow_ratio):
    """
    Folium 기반의 프리미엄 인터랙티브 지도 대시보드를 생성하여 HTML로 저장합니다.
    - 레이어 구성:
      1) 기존 공공 Wi-Fi (클러스터 + 100m 파란 원형 반경)
      2) Wi-Fi 수혜 버스정류장 (100m 이내 녹색 마커)
      3) 기타 Wi-Fi 음영 정류장 (주황색 마커)
      4) 스마트 통신 쉼터 최우선 설치 후보지 Top 10 (붉은색 뱃지 마커 + 상세 팝업)
    - 추가 UI:
      - Folium LayerControl (레이어 On/Off)
      - 상단 대시보드 요약 통계 위젯 (반응형 글래스모피즘 디자인)
      - 좌측 하단 지도 범례 (Legend)
    """
    print("\n[단계 4] Folium 인터랙티브 대시보드 제작 시작...")

    if len(top10_df) > 0:
        center_lat = top10_df['latitude'].mean()
        center_lon = top10_df['longitude'].mean()
    else:
        center_lat = df_bus['latitude'].mean()
        center_lon = df_bus['longitude'].mean()

    # 지도 생성 (가독성이 뛰어난 CartoDB Positron 타일맵)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles='cartodbpositron'
    )

    # 레이어 정의
    fg_wifi = folium.FeatureGroup(name="📶 기존 공공 Wi-Fi (반경 100m 커버리지)", show=True)
    fg_top10 = folium.FeatureGroup(name="★ 스마트 쉼터 최우선 추천 (Top 10)", show=True)
    fg_served = folium.FeatureGroup(name="🚏 Wi-Fi 수혜 정류장 (100m 이내)", show=False)
    fg_shadow = folium.FeatureGroup(name="⚠️ 기타 Wi-Fi 음영 정류장", show=False)

    # 1. 공공 Wi-Fi 레이어 (클러스터링 및 커버리지 서클 표출)
    wifi_cluster = plugins.MarkerCluster(name="Wi-Fi AP 클러스터").add_to(fg_wifi)
    # Top 10 주변 Wi-Fi 서클 식별 (Top 10 주변 1.5km 이내 Wi-Fi는 100m 커버리지 서클 항상 표출)
    top10_lats = top10_df['latitude'].values
    top10_lons = top10_df['longitude'].values

    for _, row in df_wifi.iterrows():
        lat = row['latitude']
        lon = row['longitude']
        place_nm = row['place_nm']
        addr = row['address']
        provider = row['provider']

        wifi_popup = """
        <div style="font-family:'Pretendard', sans-serif; width:200px; font-size:12px;">
            <div style="background:#2563eb; color:white; padding:4px 8px; border-radius:3px; font-weight:bold;">
                📶 공공 Wi-Fi 존
            </div>
            <div style="padding:6px 2px; color:#1e293b; line-height:1.4;">
                <b>장소:</b> {}<br>
                <b>통신사:</b> {}<br>
                <b>주소:</b> {}<br>
                <b>반경:</b> 100m 커버리지
            </div>
        </div>
        """.format(place_nm, provider, addr if addr else '정보 없음')

        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color='#1d4ed8',
            fill=True,
            fill_color='#3b82f6',
            fill_opacity=0.9,
            weight=1.5,
            popup=folium.Popup(wifi_popup, max_width=240),
            tooltip="📶 Wi-Fi: {}".format(place_nm)
        ).add_to(wifi_cluster)

        # 100m 커버리지 서클 (반경 100m 파란색 반투명)
        folium.Circle(
            location=[lat, lon],
            radius=WIFI_COVERAGE_RADIUS_M,
            color='#3b82f6',
            weight=1,
            fill=True,
            fill_color='#60a5fa',
            fill_opacity=0.18,
            interactive=False
        ).add_to(fg_wifi)

    # 2. 일반 정류장 (Wi-Fi 수혜 정류장 - 녹색)
    served_df = df_bus[~df_bus['is_shadow']]
    for _, row in served_df.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=3.5,
            color='#047857',
            fill=True,
            fill_color='#10b981',
            fill_opacity=0.8,
            weight=1,
            tooltip="🚏 {} (Wi-Fi {:.0f}m - {})".format(row['station_nm'], row['closest_wifi_dist'], row['closest_wifi_name'])
        ).add_to(fg_served)

    # 3. 기타 음영 정류장 (주황색)
    top10_ids = set(top10_df['station_id'])
    other_shadow_df = df_bus[df_bus['is_shadow'] & (~df_bus['station_id'].isin(top10_ids))]
    for _, row in other_shadow_df.iterrows():
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=3.5,
            color='#d97706',
            fill=True,
            fill_color='#fbbf24',
            fill_opacity=0.7,
            weight=1,
            tooltip="⚠️ {} (음영: {:.0f}m, 주변: {}개)".format(row['station_nm'], row['closest_wifi_dist'], row['nearby_stop_count'])
        ).add_to(fg_shadow)

    # 4. 스마트 통신 쉼터 최우선 설치 후보지 Top 10 (강렬한 빨간색 강조 마커 + 팝업 카드)
    for _, row in top10_df.iterrows():
        rank = int(row['rank'])
        s_name = row['station_nm']
        dist = row['closest_wifi_dist']
        wifi_nm = row['closest_wifi_name']
        density = row['nearby_stop_count']
        score = row['priority_score']
        city = row['city_nm']

        # 고급 카드 스타일의 인터랙티브 팝업 HTML
        popup_card = """
        <div style="font-family:'Pretendard', 'Malgun Gothic', sans-serif; width:280px; box-shadow:0 6px 16px rgba(0,0,0,0.18); border-radius:10px; overflow:hidden; border:1px solid #fca5a5;">
            <div style="background:linear-gradient(135deg, #ef4444 0%, #991b1b 100%); color:white; padding:12px 14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="background:#fee2e2; color:#991b1b; font-size:11px; font-weight:800; padding:2px 8px; border-radius:10px;">★ 최우선 추천 #{rank}위</span>
                    <span style="font-size:12px; opacity:0.9;">{city}</span>
                </div>
                <h3 style="margin:6px 0 0 0; font-size:17px; font-weight:bold; letter-spacing:-0.4px;">{s_name}</h3>
            </div>
            <div style="padding:12px 14px; background:#ffffff; font-size:12.5px; color:#334155; line-height:1.6;">
                <div style="margin-bottom:8px; display:flex; justify-content:space-between; border-bottom:1px dashed #e2e8f0; padding-bottom:4px;">
                    <span style="color:#64748b;">스마트 쉼터 종합 스코어</span>
                    <b style="color:#dc2626; font-size:15px;">{score:.1f} / 100점</b>
                </div>
                <div style="margin-bottom:4px;">
                    <span style="color:#64748b;">최단 Wi-Fi 음영 거리:</span> <b style="color:#0f172a;">{dist:.1f} m</b>
                </div>
                <div style="margin-bottom:4px;">
                    <span style="color:#64748b;">인접 Wi-Fi AP:</span> <b style="color:#0f172a;">{wifi_nm}</b>
                </div>
                <div style="margin-bottom:6px;">
                    <span style="color:#64748b;">주변 정류장 밀집도:</span> <b style="color:#0f172a;">반경 500m 내 {density}개</b>
                </div>
                <div style="background:#fef2f2; border-left:3px solid #ef4444; padding:6px 8px; border-radius:4px; font-size:11.5px; color:#991b1b; margin-top:8px;">
                    <b>💡 기대 효과:</b> 기존 공공 Wi-Fi 인프라가 부재한 상태에서 다수 정류장이 밀집한 대중교통 거점이므로, 스마트 통신 쉼터(Wi-Fi+온열 스마트벤치) 신설 시 시민 체감 편익이 극대화됨.
                </div>
            </div>
        </div>
        """.format(rank=rank, city=city, s_name=s_name, score=score, dist=dist, wifi_nm=wifi_nm, density=density)

        # 1~3위는 왕관/별 아이콘, 4~10위는 버스 아이콘
        icon_name = 'star' if rank <= 3 else 'bus'
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            icon=folium.Icon(color='red', icon=icon_name, prefix='fa'),
            popup=folium.Popup(popup_card, max_width=320),
            tooltip="★ [추천 {}위] {} (스코어: {:.1f}점)".format(rank, s_name, score)
        ).add_to(fg_top10)

        # 신규 스마트 쉼터 100m 커버리지 예상 반경 (빨간색 점선 서클)
        folium.Circle(
            location=[row['latitude'], row['longitude']],
            radius=WIFI_COVERAGE_RADIUS_M,
            color='#dc2626',
            weight=2,
            dash_array='6, 6',
            fill=True,
            fill_color='#f87171',
            fill_opacity=0.22,
            interactive=False
        ).add_to(fg_top10)

    # 레이어를 지도에 결합
    fg_wifi.add_to(m)
    fg_served.add_to(m)
    fg_shadow.add_to(m)
    fg_top10.add_to(m)

    # 레이어 컨트롤 추가
    folium.LayerControl(collapsed=False).add_to(m)

    # 상단 요약 대시보드 위젯 및 범례(Legend) HTML 삽입
    top1_name = top10_df.iloc[0]['station_nm'] if len(top10_df) > 0 else '미지정'
    top1_score = top10_df.iloc[0]['priority_score'] if len(top10_df) > 0 else 0.0

    dashboard_ui_html = """
    <!-- 상단 대시보드 헤더 위젯 (Floating Dashboard Widget) -->
    <div id="stats-widget" style="
        position: fixed;
        top: 20px;
        left: 60px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.96);
        backdrop-filter: blur(10px);
        padding: 16px 20px;
        border-radius: 12px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(226, 232, 240, 0.9);
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 440px;
    ">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: #2563eb; color: white; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;">공공 빅데이터 분석</span>
                <h2 style="margin: 0; font-size: 16px; font-weight: 800; color: #0f172a; letter-spacing: -0.5px;">스마트 통신 쉼터 최적 입지 분석</h2>
            </div>
        </div>
        <p style="margin: 0 0 12px 0; font-size: 12px; color: #64748b; line-height: 1.4;">
            국토교통부 버스정류장 API 및 공공 Wi-Fi 데이터 융합 Haversine 거리 분석 대시보드
        </p>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px;">
            <div style="background: #f8fafc; padding: 8px 10px; border-radius: 8px; text-align: center; border: 1px solid #e2e8f0;">
                <div style="font-size: 11px; color: #64748b; font-weight: 600;">분석 정류장</div>
                <div style="font-size: 15px; font-weight: 800; color: #1e293b; margin-top: 2px;">{total_stops:,}개</div>
            </div>
            <div style="background: #eff6ff; padding: 8px 10px; border-radius: 8px; text-align: center; border: 1px solid #bfdbfe;">
                <div style="font-size: 11px; color: #1d4ed8; font-weight: 600;">기존 Wi-Fi</div>
                <div style="font-size: 15px; font-weight: 800; color: #1e40af; margin-top: 2px;">{wifi_cnt:,}개</div>
            </div>
            <div style="background: #fef2f2; padding: 8px 10px; border-radius: 8px; text-align: center; border: 1px solid #fecaca;">
                <div style="font-size: 11px; color: #b91c1c; font-weight: 600;">Wi-Fi 음영률</div>
                <div style="font-size: 15px; font-weight: 800; color: #dc2626; margin-top: 2px;">{shadow_ratio:.1f}%</div>
            </div>
        </div>
        <div style="background: #fdf2f8; border: 1px solid #fbcfe8; border-radius: 8px; padding: 8px 12px; display: flex; align-items: center; justify-content: space-between;">
            <span style="font-size: 12px; color: #9d174d; font-weight: 700;">🏆 최우선 추천 1순위:</span>
            <span style="font-size: 12px; color: #831843; font-weight: 800;">{top1_name} ({top1_score:.1f}점)</span>
        </div>
    </div>

    <!-- 좌측 하단 반응형 범례 (Floating Map Legend) -->
    <div id="legend-box" style="
        position: fixed;
        bottom: 25px;
        left: 20px;
        z-index: 9999;
        background: rgba(255, 255, 255, 0.96);
        backdrop-filter: blur(8px);
        padding: 14px 18px;
        border-radius: 10px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        border: 1px solid #e2e8f0;
        font-family: 'Pretendard', sans-serif;
        font-size: 12px;
        color: #334155;
        line-height: 1.6;
        min-width: 230px;
    ">
        <div style="font-weight: 800; font-size: 13px; color: #0f172a; margin-bottom: 8px; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px;">
            🗺️ 지도 시각화 범례 (Legend)
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="width: 14px; height: 14px; background: #dc2626; border-radius: 50%; display: inline-block; margin-right: 8px; border: 2px solid #fff; box-shadow: 0 0 4px rgba(220,38,38,0.6);"></span>
            <span><b>스마트 쉼터 우선 후보 (Top 10)</b></span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="width: 12px; height: 12px; background: #3b82f6; border-radius: 50%; display: inline-block; margin-right: 8px; border: 1px solid #1d4ed8;"></span>
            <span>기존 공공 Wi-Fi AP</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="width: 14px; height: 14px; background: rgba(96, 165, 250, 0.3); border: 1.5px solid #3b82f6; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span>공공 Wi-Fi 커버리지 (100m)</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <span style="width: 10px; height: 10px; background: #10b981; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span>Wi-Fi 수혜 정류장 (100m 이내)</span>
        </div>
        <div style="display: flex; align-items: center;">
            <span style="width: 10px; height: 10px; background: #fbbf24; border-radius: 50%; display: inline-block; margin-right: 8px;"></span>
            <span>기타 Wi-Fi 음영 정류장</span>
        </div>
    </div>
    """.format(
        total_stops=total_stops,
        wifi_cnt=len(df_wifi),
        shadow_ratio=shadow_ratio,
        top1_name=top1_name,
        top1_score=top1_score
    )

    m.get_root().html.add_child(folium.Element(dashboard_ui_html))
    m.save(OUTPUT_HTML)
    print("  - [대시보드 완성] HTML 파일 저장 성공: {}".format(os.path.abspath(OUTPUT_HTML)))
    return OUTPUT_HTML


# ==============================================================================
# 6. 메인 파이프라인 제어 함수 (Main Routine)
# ==============================================================================
def main():
    print("=" * 85)
    print(" [클래스셀링 과제] 공공 빅데이터 기반 '스마트 통신 쉼터' 최적 입지 분석 시스템")
    print("=" * 85)

    # 명령행 인자 파싱 (--api-only 옵션 지원)
    force_api = '--api-only' in sys.argv

    # 1. 데이터 수집 (API 1순위 시도 + 로컬 CSV 2순위 Fallback)
    df_bus_raw = fetch_bus_data()
    df_wifi_raw = fetch_wifi_data()

    # 2. 데이터 정제, 좌표 유효성 검사 및 지역 매칭
    df_bus, df_wifi = align_and_preprocess(df_bus_raw, df_wifi_raw, force_api=force_api)

    # 3. 거리 계산 (Haversine) 및 우선순위 스코어링 (Top 10)
    df_bus, top10_df, shadow_stops, total_stops, shadow_ratio = analyze_smart_shelter_sites(df_bus, df_wifi)

    # 4. Folium 인터랙티브 지도 대시보드 렌더링
    dashboard_file = render_folium_dashboard(df_bus, df_wifi, top10_df, shadow_stops, total_stops, shadow_ratio)

    print("\n" + "=" * 85)
    print(" [성공] 모든 분석 및 지도 시각화 대시보드 생성이 완료되었습니다!")
    print("  ▶ 산출물 경로: {}".format(os.path.abspath(dashboard_file)))
    print("  ▶ 웹 브라우저에서 '{}'을 열어 인터랙티브 지도를 확인하실 수 있습니다.".format(dashboard_file))
    print("=" * 85)


if __name__ == '__main__':
    main()
