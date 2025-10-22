import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request
from datetime import datetime
import os
import re  # 괄호 제거를 위해 re 모듈 추가

html = 'miri.html' #여기를 index.html로 바꾸면 미리캔버스 없이 볼 수 있어

app = Flask(__name__)

# --- 3. 학교명 변환 딕셔너리 ---
SCHOOL_ALIAS_MAP = {
    "대현고": "대현고등학교",
    "강남고": "강남고등학교",
    # 필요한 학교들을 여기에 추가합니다.
    "신선여고": "신선여자고등학교",
    "홈플공고": "대현고등학교"
}


def get_full_school_name(alias):
    """약칭을 정식 학교명으로 변환하는 함수."""
    if alias in SCHOOL_ALIAS_MAP:
        return SCHOOL_ALIAS_MAP[alias]
    elif alias.endswith("고"):
        return alias + "등학교"
    else:
        return alias


# --- 4. 크롤링 설정 및 링크 리스트 ---
# !! 중요: 실제 크롤링할 웹사이트의 URL과 HTML Class로 반드시 수정해야 합니다 !!
CRAWL_CONFIG = {
    # 학교명에 따라 사용할 기본 링크를 리스트로 정의
    "base_urls": [
        "https://school.use.go.kr/daehyun-h/M01030701/list?ymd=",  # list의 0번 링크 (대현고등학교용)
        "https://school.use.go.kr/ugn-h/M01040201/list?ymd=",
        "https://school.use.go.kr/shinsun-h/M01030702/list?ymd=",
        "https://school.use.go.kr/hwaam-h/M01030602/list?ymd=",
        # 여기에 다른 학교의 기본 URL을 추가할 수 있습니다.
    ],
    # [수정] 크롤링 대상 클래스를 "tch-lnc"로 한정
    "target_class": "tch-lnc"
}


def perform_crawling(school_name, formatted_date, original_date_str):
    """
    학교명과 YYYYMMDD 형식의 날짜를 사용하여 데이터를 크롤링하고 결과를 반환합니다.
    URL 형식: [base_url]/[YYYYMMDD]
    """

    # 학교명에 따라 base_url 선택 로직 (list 인덱스 사용)
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

    # [수정] URL 경로에 formatted_date를 직접 결합 (슬래시(/) 없이)
    # 예: "https://daehyeon-school.example.com/api/info" + "20250429"
    target_url = f"{base_url}{formatted_date}"
    print(f"DEBUG: 크롤링 대상 URL: {target_url}")

    # --- 크롤링 로직 시작 ---
    try:
        response = requests.get(target_url, timeout=10)
        response.raise_for_status()  # 4xx, 5xx 에러 발생 시 예외 처리

        soup = BeautifulSoup(response.text, 'html.parser')

        # [수정] CRAWL_CONFIG["target_class"]를 사용하여 데이터 컨테이너 찾기
        data_container = soup.find(class_=CRAWL_CONFIG["target_class"])

        if data_container:
            # 찾은 컨테이너 내부의 모든 텍스트를 추출하여 반환
            return data_container.get_text(strip=True, separator='\n')
        else:
            return f"크롤링 오류: {school_name} ({original_date_str})에 해당하는 'tch-lnc' 클래스의 데이터를 찾을 수 없습니다."

    except requests.exceptions.RequestException as e:
        return f"크롤링 중 네트워크 또는 HTTP 오류 발생. URL: {target_url}, 오류: {e}"
    except Exception as e:
        return f"데이터 처리 중 예상치 못한 오류 발생: {e}"


# --- 1. 백엔드 라우트 설정 (메인 페이지) ---
@app.route('/', methods=['GET'])
def index():
    """초기 페이지 로드."""
    return render_template(html, result=None)


# --- 2. 입력 및 5. 결과 출력 처리 ---
@app.route('/scrape', methods=['POST'])
def scrape_data():
    """프론트엔드 입력 처리, 학교명 변환, 날짜 변환, 크롤링 실행."""

    school_alias = request.form.get('school_name', '').strip()
    target_date_input = request.form.get('date', '').strip()  # 사용자 입력 날짜 (YYYY-MM-DD)

    if not school_alias or not target_date_input:
        return render_template(html, result="학교명과 날짜를 모두 입력해 주세요.", school="오류", date="오류")

    # 날짜 형식 변환 로직 (YYYY-MM-DD -> YYYYMMDD)
    try:
        date_obj = datetime.strptime(target_date_input, '%Y-%m-%d')
        formatted_date_for_url = date_obj.strftime('%Y%m%d')

        # [수정 1] 출력용 날짜 형식 변환 (N월 M일)
        display_date = f"{date_obj.month}월 {date_obj.day}일"

    except ValueError:
        return render_template(html, result="잘못된 날짜 형식입니다. (YYYY-MM-DD 형식 확인)", school="오류", date="오류")

    # 3. 학교명 변환
    full_school_name = get_full_school_name(school_alias)

    # 4. 크롤링 실행
    crawled_data = perform_crawling(
        full_school_name,
        formatted_date_for_url,  # YYYYMMDD 형식으로 크롤링 함수에 전달
        target_date_input
    )

    # [수정 2] 크롤링 결과에서 괄호() 안의 내용과 괄호 자체를 제거
    if crawled_data and not crawled_data.startswith("크롤링 오류"):
        # 정규 표현식: \(.*?\): 여는 괄호, 닫는 괄호 및 그 사이의 모든 문자를 찾습니다.
        crawled_data = re.sub(r'\(.*?\)', '', crawled_data).strip()

    # 5. 결과를 프론트엔드로 전달
    return render_template(html,
                           result=crawled_data,
                           school=full_school_name,
                           date=display_date)  # N월 M일 형식의 display_date 사용


if __name__ == '__main__':
    # Flask 앱 실행
    app.run(debug=True)
