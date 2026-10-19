# -*- coding: utf-8 -*-
"""
스마트 통신 쉼터 전역 설정 모듈 (config.py)
.env 파일로부터 모든 API 키 및 서버 설정을 로드하여 전역 변수로 제공합니다.

[사용법]
    import config
    print(config.BUS_API_KEY)
    print(config.KAKAO_JS_KEY)
    print(config.PORT)
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")


def _load_env_file(filepath):
    """
    python-dotenv 라이브러리가 없어도 순수 표준 라이브러리로
    .env 파일의 키=값 쌍을 안전하게 파싱하여 os.environ에 주입합니다.
    """
    if not os.path.exists(filepath):
        return

    try:
        # 1차 시도: python-dotenv 활용
        from dotenv import load_dotenv
        load_dotenv(filepath, override=True)
    except ImportError:
        # 2차 시도: 내장 파서 fallback
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key not in os.environ:
                    os.environ[key] = val


# .env 파일 로드 실행
_load_env_file(ENV_FILE)

# ==============================================================================
# 전역 설정 변수 정의 (Global Configurations)
# ==============================================================================

# 1. 공공데이터포털 통합 Open API 인증키 (국토교통부 버스 및 한국관광공사 TourAPI 공통)
PUBLIC_DATA_PORTAL_API_KEY = (
    os.environ.get("PUBLIC_DATA_PORTAL_API_KEY") or
    os.environ.get("공공데이터포털_API_KEY") or
    os.environ.get("공공데이터포털_api_key") or
    os.environ.get("DATA_GO_KR_API_KEY") or
    os.environ.get("BUS_API_KEY") or
    ""
).strip()
BUS_API_KEY = PUBLIC_DATA_PORTAL_API_KEY  # 기존 코드 호환성 유지

# 2. 카카오 지도 JavaScript API 키 (.env 로드)
KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "").strip()

# 3. 웹 서버 바인딩 호스트 및 포트
HOST = os.environ.get("HOST", "0.0.0.0")
try:
    PORT = int(os.environ.get("PORT", 5000))
except ValueError:
    PORT = 5000

# 4. 기본 선택 지역 코드
DEFAULT_REGION = os.environ.get("DEFAULT_REGION", "busan")

# 5. 공공 Open API 엔드포인트 URL
API_ENDPOINT = "http://api.odcloud.kr/api/15067528/v1/uddi:eb02ec03-6edd-4cb0-88b8-eda22ca55e80"
TOUR_API_ENDPOINT = "http://apis.data.go.kr/B551011/KorService1/searchFestival1"
TOUR_API_BACKUP = "http://api.visitkorea.or.kr/openapi/service/rest/KorService/searchFestival"

# 6. 한국방송통신전파진흥원(KCA) 산악지역 이동통신 기지국 Open API 키 및 엔드포인트
MOUNTAIN_API_KEY = (
    os.environ.get("MOUNTAIN_API_KEY") or
    os.environ.get("KCA_API_KEY") or
    os.environ.get("SPECTRUM_API_KEY") or
    ""
).strip()
MOUNTAIN_API_ENDPOINT = "https://spectrummap.kr/openapiNew.do"

# 7. 공공 Wi-Fi 데이터 자동 다운로드 URL 및 갱신 주기 (TTL)
try:
    DATA_UPDATE_TTL = int(os.environ.get("data_update_ttl", os.environ.get("DATA_UPDATE_TTL", 86400)))
except ValueError:
    DATA_UPDATE_TTL = 86400

LOCALDATA_WIFI_DOWNLOAD_URL = "https://file.localdata.go.kr/file/download/free_wifi_info/info"
LOCALDATA_WIFI_REFERER = "https://file.localdata.go.kr/file/free_wifi_info/info"

# 7. 주요 파일 경로 (작업폴더 루트에는 public_wifi_data.csv 단일 파일만 유지 및 사용)
WIFI_CSV_PATH = os.path.join(BASE_DIR, "public_wifi_data.csv")
BUS_CSV_PATH = os.path.join(BASE_DIR, "bus_stops.csv")
NATIONAL_BUS_CSV = BUS_CSV_PATH
BUSAN_WIFI_CSV = WIFI_CSV_PATH
BACKUP_BUS_CSV = BUS_CSV_PATH

# 8. 분석 기준 파라미터 및 유효 좌표 범위 (대한민국 영토)
LAT_MIN, LAT_MAX = 33.0, 39.0
LON_MIN, LON_MAX = 124.0, 132.0

WIFI_COVERAGE_RADIUS_M = 100.0   # 공공 Wi-Fi 유효 커버리지 반경 (100m)
DENSITY_RADIUS_M = 500.0         # 주변 정류장 밀집도 측정 반경 (500m)
EARTH_RADIUS_M = 6371000.0       # 지구 반지름 (미터)

# 8. 대한민국 시·도 지역 사전 정의 (코드, 명칭, 지도 중심좌표, 기본 줌 레벨, 필터 키워드)
REGION_REGISTRY = {
    'busan': {
        'code': 'busan',
        'name': '부산광역시',
        'short_name': '부산',
        'lat': 35.1796,
        'lon': 129.0756,
        'zoom': 12,
        'keywords': ['부산']
    },
    'seoul': {
        'code': 'seoul',
        'name': '서울특별시',
        'short_name': '서울',
        'lat': 37.5665,
        'lon': 126.9780,
        'zoom': 12,
        'keywords': ['서울']
    },
    'gyeonggi': {
        'code': 'gyeonggi',
        'name': '경기도',
        'short_name': '경기',
        'lat': 37.4138,
        'lon': 127.5183,
        'zoom': 10,
        'keywords': ['경기']
    },
    'incheon': {
        'code': 'incheon',
        'name': '인천광역시',
        'short_name': '인천',
        'lat': 37.4563,
        'lon': 126.7052,
        'zoom': 12,
        'keywords': ['인천']
    },
    'daejeon': {
        'code': 'daejeon',
        'name': '대전광역시',
        'short_name': '대전',
        'lat': 36.3504,
        'lon': 127.3845,
        'zoom': 12,
        'keywords': ['대전']
    },
    'daegu': {
        'code': 'daegu',
        'name': '대구광역시',
        'short_name': '대구',
        'lat': 35.8714,
        'lon': 128.6014,
        'zoom': 12,
        'keywords': ['대구']
    },
    'gwangju': {
        'code': 'gwangju',
        'name': '광주광역시',
        'short_name': '광주',
        'lat': 35.1595,
        'lon': 126.8526,
        'zoom': 12,
        'keywords': ['광주']
    },
    'ulsan': {
        'code': 'ulsan',
        'name': '울산광역시',
        'short_name': '울산',
        'lat': 35.5384,
        'lon': 129.3114,
        'zoom': 12,
        'keywords': ['울산']
    },
    'sejong': {
        'code': 'sejong',
        'name': '세종특별자치시',
        'short_name': '세종',
        'lat': 36.4800,
        'lon': 127.2890,
        'zoom': 12,
        'keywords': ['세종']
    },
    'jeju': {
        'code': 'jeju',
        'name': '제주특별자치도',
        'short_name': '제주',
        'lat': 33.4996,
        'lon': 126.5312,
        'zoom': 11,
        'keywords': ['제주']
    },
    'gyeongnam': {
        'code': 'gyeongnam',
        'name': '경상남도',
        'short_name': '경남',
        'lat': 35.4606,
        'lon': 128.2132,
        'zoom': 10,
        'keywords': ['경상남도', '창원', '김해', '진주', '양산', '거제']
    },
    'gyeongbuk': {
        'code': 'gyeongbuk',
        'name': '경상북도',
        'short_name': '경북',
        'lat': 36.5760,
        'lon': 128.5056,
        'zoom': 10,
        'keywords': ['경상북도', '안동', '포항', '구미', '경주']
    },
    'gangwon': {
        'code': 'gangwon',
        'name': '강원특별자치도',
        'short_name': '강원',
        'lat': 37.8228,
        'lon': 128.1555,
        'zoom': 10,
        'keywords': ['강원']
    },
    'chungnam': {
        'code': 'chungnam',
        'name': '충청남도',
        'short_name': '충남',
        'lat': 36.5184,
        'lon': 126.8000,
        'zoom': 10,
        'keywords': ['충청남도', '천안', '아산', '서산']
    },
    'chungbuk': {
        'code': 'chungbuk',
        'name': '충청북도',
        'short_name': '충북',
        'lat': 36.6357,
        'lon': 127.4912,
        'zoom': 10,
        'keywords': ['충청북도', '청주', '충주', '제천']
    },
    'jeonnam': {
        'code': 'jeonnam',
        'name': '전라남도',
        'short_name': '전남',
        'lat': 34.8679,
        'lon': 126.9910,
        'zoom': 10,
        'keywords': ['전라남도', '목포', '여수', '순천']
    },
    'jeonbuk': {
        'code': 'jeonbuk',
        'name': '전북특별자치도',
        'short_name': '전북',
        'lat': 35.7175,
        'lon': 127.1530,
        'zoom': 10,
        'keywords': ['전북', '전라북도', '전주', '익산', '군산']
    }
}
