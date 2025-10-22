import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from datetime import datetime
import os
import re

# --- 1. 파일 경로 설정 ---
# NOTE: Render 환경에서는 템플릿 파일을 'templates' 폴더에 넣고 경로를 'miri.html'로만 지정하는 것이 안전합니다.
# 'templates/miri.html' 파일이 존재한다고 가정합니다.
html_template_name = 'miri.html'

app = Flask(__name__)

# --- 2. 학교명 변환 딕셔너리 ---
SCHOOL_ALIAS_MAP = {
    "대현고": "대현고등학교",
    "강남고": "강남고등학교",
    "신선여고": "신선여자고등학교",
    "홈플공고": "대현고등학교" # 이 약칭은 대현고로 변환됨
}


def get_full_school_name(alias):
    """약칭을 정식 학교명으로 변환하는 함수."""
    if alias in SCHOOL_ALIAS_MAP:
        return SCHOOL_ALIAS_MAP[alias]
    elif alias.endswith("고"):
        return alias + "등학교"
    else:
        return alias


# --- 3. 크롤링 설정 및 링크 리스트 ---
CRAWL_CONFIG = {
    # 학교명에 따라 사용할 기본 링크를 리스트로 정의
    "base_urls": [
        "https://school.use.go.kr/daehyun-h/M01030701/list?ymd=",  # 0: 대현고등학교용
        "https://school.use.go.kr/ugn-h/M01040201/list?ymd=",       # 1: 강남고등학교용
        "https://school.use.go.kr/shinsun-h/M01030702/list?ymd=",  # 2: 신선여자고등학교용
        "https://school.use.go.kr/hwaam-h/M01030602/list?ymd=",    # 3: 화암고등학교용
        # 다른 학교의 기본 URL은 여기에 추가
    ],
    "target_class": "tch-lnc"
}


def perform_crawling(school_name, formatted_date, original_date_str):
    """
    학교명과 YYYYMMDD 형식의 날짜를 사용하여 데이터를 크롤링하고 결과를 반환합니다.
    """

    # 학교명에 따라 base_url 선택 로직
    base_url = None
    if school_name == "대현고등학교":
        base_url = CRAWL_CONFIG["base_urls"][0]
    elif school_name == "강남고등학교":
        base_url = CRAWL_CONFIG["base_urls"][1]
    elif school_name == "신선여자고등학교":
        base_url = CRAWL_CONFIG["base_urls"][2]
    elif school_name == "화암고등학교":
        base_url = CRAWL_CONFIG["base_urls"][3]
    else:
        return f"크롤링 오류: 등록되지 않은 학교명({school_name})입니다. 링크를 찾을 수 없습니다."

    target_url = f"{base_url}{formatted_date}"
    print(f"DEBUG: 크롤링 대상 URL: {target_url}")

    # --- 크롤링 로직 시작 ---
    try:
        # Render 환경 IP 차단 회피를 위한 User-Agent 헤더 추가
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()  # 4xx, 5xx 에러 발생 시 예외 처리

        soup = BeautifulSoup(response.text, 'html.parser')

        # CRAWL_CONFIG["target_class"]를 사용하여 데이터 컨테이너 찾기
        data_container = soup.find(class_=CRAWL_CONFIG["target_class"])

        if data_container:
            # 찾은 컨테이너 내부의 모든 텍스트를 추출하여 반환
            return data_container.get_text(strip=True, separator='\n')
        else:
            # HTML을 받아왔으나 클래스를 찾지 못한 경우
            print(f"DEBUG: 크롤링 실패. HTML 첫 500자: {response.text[:500]}")
            return f"크롤링 오류: {school_name} ({original_date_str})에 해당하는 '{CRAWL_CONFIG['target_class']}' 클래스의 데이터를 찾을 수 없습니다."

    except requests.exceptions.RequestException as e:
        # 네트워크 또는 HTTP 오류 발생 (예: Timeout, 404, Connection Refused)
        return f"크롤링 중 네트워크 또는 HTTP 오류 발생. URL: {target_url}, 오류: {e}"
    except Exception as e:
        return f"데이터 처리 중 예상치 못한 오류 발생: {e}"


# ----------------------------------------------------------------------
# --- 4. 백엔드 라우트 설정 ---
@app.route('/', methods=['GET'])
def index():
    """초기 페이지 로드."""
    return render_template(html_template_name, result=None)


@app.route('/scrape', methods=['POST'])
def scrape_data():
    """프론트엔드 입력 처리, 학교명 변환, 날짜 변환, 크롤링 실행."""

    school_alias = request.form.get('school_name', '').strip()
    target_date_input = request.form.get('date', '').strip()

    if not school_alias or not target_date_input:
        return render_template(html_template_name, result="학교명과 날짜를 모두 입력해 주세요.", school="오류", date="오류")

    # 날짜 형식 변환 로직 (YYYY-MM-DD -> YYYYMMDD)
    try:
        date_obj = datetime.strptime(target_date_input, '%Y-%m-%d')
        formatted_date_for_url = date_obj.strftime('%Y%m%d')

        # 출력용 날짜 형식 변환 (N월 M일)
        display_date = f"{date_obj.month}월 {date_obj.day}일"

    except ValueError:
        return render_template(html_template_name, result="잘못된 날짜 형식입니다. (YYYY-MM-DD 형식 확인)", school="오류", date="오류")

    # 학교명 변환
    full_school_name = get_full_school_name(school_alias)

    # 크롤링 실행
    crawled_data = perform_crawling(
        full_school_name,
        formatted_date_for_url,
        target_date_input
    )

    # 크롤링 결과에서 괄호() 안의 내용과 괄호 자체를 제거
    if crawled_data and not crawled_data.startswith("크롤링 오류"):
        crawled_data = re.sub(r'\(.*?\)', '', crawled_data).strip()

    # 결과를 프론트엔드로 전달
    return render_template(html_template_name,
                           result=crawled_data,
                           school=full_school_name,
                           date=display_date)


# ----------------------------------------------------------------------
# Render 환경에서는 Gunicorn과 같은 WSGI 서버가 app 객체를 직접 실행합니다.
# 로컬 개발 환경에서만 app.run()을 사용합니다.
if __name__ == '__main__':
    # 로컬 개발 환경에서만 사용
    app.run(debug=True)
