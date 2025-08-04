import json
import os
import requests
import datetime
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 구글 캘린더 API가 허용할 권한 범위
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_health_data() -> str:
    """
    사용자의 최신 건강 데이터를 가져옵니다.
    (현재는 로컬 샘플 파일을 읽어오는 것으로 시뮬레이션합니다.)
    """
    print("TOOL CALLED: get_health_data()")
    try:
        # main.py와 같은 위치에 있는 data 폴더를 참조합니다.
        with open("data/sample_data.json", "r", encoding="utf-8") as f:
            return json.dumps(json.load(f))
    except FileNotFoundError:
        return json.dumps({"error": "sample_data.json 파일을 찾을 수 없습니다."})


def Youtube(query: str) -> str:
    """
    주어진 검색어로 유튜브에서 관련 영상을 검색합니다.
    (현재는 검색할 내용을 출력하는 것으로 시뮬레이션합니다.)
    """
    print(f"TOOL CALLED: Youtube(query='{query}')")
    encoded_query = query.replace(' ', '+')
    return f"'{query}'에 대한 유튜브 검색 결과 링크: https://www.youtube.com/results?search_query={encoded_query}"


def google_calendar_create_event(title: str, start_time: str, end_time: str) -> str:
    """
    주어진 제목과 시간으로 구글 캘린더에 새 이벤트를 생성합니다.
    start_time, end_time은 'YYYY-MM-DDTHH:MM:SS' 형식의 ISO 8601 문자열이어야 합니다.
    (예: '2025-08-05T10:00:00')
    """
    print(f"TOOL CALLED: google_calendar_create_event(title='{title}')")
    creds = None
    # token.json 파일은 사용자 인증 정보를 저장합니다.
    # 파일이 이미 있으면 자동으로 로그인 정보를 불러옵니다.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # 유효한 인증 정보가 없으면 사용자가 로그인하도록 합니다.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # credentials.json 파일이 필요합니다.
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # 다음 실행을 위해 인증 정보를 저장합니다.
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("calendar", "v3", credentials=creds)

        # API에 전달할 이벤트 객체를 생성합니다.
        event = {
            "summary": title,
            "description": "WellnessCoachAI를 통해 생성된 일정입니다.",
            "start": {
                "dateTime": start_time,
                "timeZone": "Asia/Seoul", # 한국 시간대
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "Asia/Seoul",
            },
        }

        # API를 호출하여 이벤트를 생성합니다.
        event = service.events().insert(calendarId="primary", body=event).execute()

        # 성공 메시지를 반환합니다.
        return f"구글 캘린더에 '{event.get('summary')}' 일정이 성공적으로 등록되었습니다. ({event.get('htmlLink')})"

    except HttpError as error:
        # API 오류 발생 시 에러 메시지를 반환합니다.
        return f"일정 생성 중 오류가 발생했습니다: {error}"

def get_weather(location: str) -> str:
    """
    주어진 위치의 현재 날씨 정보를 가져옵니다.
    (현재는 '맑음'으로 시뮬레이션합니다.)
    """
    print(f"TOOL CALLED: get_weather(location='{location}')")
    return f"현재 {location}의 날씨는 '맑음'이며, 야외 활동하기 좋은 날씨입니다."


def find_nearby_places(query: str) -> str:
    """
    주어진 검색어로 주변 장소를 찾습니다. (예: '동작구 주변 한의원')
    Naver Developers의 '검색' API를 사용합니다.
    """
    print(f"TOOL CALLED: find_nearby_places(query='{query}')")

    # .env 파일에서 Naver Developers API 키를 불러옵니다.
    client_id = os.getenv("NAVER_DEV_CLIENT_ID")
    client_secret = os.getenv("NAVER_DEV_CLIENT_SECRET")

    if not client_id or not client_secret:
        return "Naver Developers API 인증 정보가 설정되지 않았습니다. .env 파일을 확인해주세요."

    # Naver 검색(지역) API 엔드포인트 URL
    url = "https://openapi.naver.com/v1/search/local.json"
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": 5,  # 최대 5개의 결과를 가져옴
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        
        if not data.get("items"):
            return f"'{query}'에 대한 검색 결과가 없습니다."

        results = []
        for item in data["items"]:
            # API 응답에 포함된 HTML 태그(<b>, </b>)를 제거합니다.
            title = item.get("title", "").replace("<b>", "").replace("</b>", "")
            address = item.get("address", "")
            results.append(f"- {title} ({address})")

        return f"'{query}'에 대한 주변 장소 검색 결과입니다:\n" + "\n".join(results)

    except requests.exceptions.HTTPError as http_err:
        print(f"--- NAVER API HTTP ERROR --- \n{http_err}\nResponse: {response.text}\n-----------------------")
        return f"장소 검색 중 서버 오류가 발생했습니다 (코드: {response.status_code}). API 키와 사용 권한을 다시 확인해주세요."
    except Exception as e:
        print(f"--- UNKNOWN ERROR --- \n{e}\n---------------------")
        return f"주변 장소 검색 중 알 수 없는 오류가 발생했습니다: {e}"