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
from typing import Optional 

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


# multi_tool_agent/tools.py

def Youtube(query: str) -> str:
    """
    주어진 검색어로 유튜브에서 관련성 높은 영상 1개를 검색하여 링크를 반환합니다.
    """
    print(f"TOOL CALLED: Youtube(query='{query}')")
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return "YouTube API 키가 설정되지 않았습니다."

    try:
        youtube_service = build('youtube', 'v3', developerKey=api_key)
        
        request = youtube_service.search().list(
            q=query,
            part='snippet',
            type='video',
            maxResults=5,
            relevanceLanguage='ko'
        )
        response = request.execute()
        
        if not response.get('items'):
            return f"'{query}'에 대한 유튜브 영상을 찾을 수 없습니다."
            
        results = []
        for item in response['items']:
            video_id = item['id']['videoId']
            video_title = item['snippet']['title']
            link = f"https://www.youtube.com/watch?v={video_id}"
            results.append(f"- {video_title}\n  (링크: {link})")
        
        return f"'{query}' 관련 영상: '{video_title}'\n링크: https://www.youtube.com/watch?v={video_id}"

    except Exception as e:
        return f"유튜브 검색 중 오류가 발생했습니다: {e}"


def _get_calendar_credentials() -> Credentials | None:
    """
    Google Calendar API 인증을 처리하고, 유효한 Credentials 객체를 반환합니다.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"❌ 토큰 갱신 중 치명적인 오류 발생: {e}")
                os.remove("token.json")
                return None
        else:
            try:
                # 💥 모든 종류의 오류를 잡기 위해 try-except 블록 강화
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError("오류: credentials.json 파일을 찾을 수 없습니다. API 설정이 필요합니다.")
                
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                # FileNotFoundError 외에 JSON 형식 오류, 키 값 오류 등 모든 것을 잡아냅니다.
                print(f"❌ 인증 흐름 생성 중 치명적인 오류 발생: {e}")
                return None
        
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            
    return creds

# multi_tool_agent/tools.py

def google_calendar_create_single_event(title: str, start_time: str, end_time: str) -> str:
    """
    주어진 제목과 시간으로 구글 캘린더에 단일 이벤트를 생성합니다.
    Args:
        title (str): 이벤트 제목.
        start_time (str): 시작 시간 ('YYYY-MM-DDTHH:MM:SS' 형식).
        end_time (str): 종료 시간 ('YYYY-MM-DDTHH:MM:SS' 형식).
    """
    print(f"TOOL CALLED: google_calendar_create_single_event(title='{title}')")
    creds = _get_calendar_credentials()
    if not creds: return "Google Calendar 인증에 실패했습니다."

    try:
        service = build("calendar", "v3", credentials=creds)
        event_body = {
            "summary": title,
            "description": "WellnessCoachAI를 통해 생성된 일정입니다.",
            "start": {"dateTime": start_time, "timeZone": "Asia/Seoul"},
            "end": {"dateTime": end_time, "timeZone": "Asia/Seoul"},
        }
        created_event = service.events().insert(calendarId="primary", body=event_body).execute()
        return f"✅ 구글 캘린더에 '{title}' 일정을 성공적으로 등록했습니다. 링크: {created_event.get('htmlLink', '')}"
    except Exception as e:
        return f"❌ 단일 일정 생성 중 오류 발생: {e}"

def google_calendar_create_recurring_event(title: str, start_time: str, end_time: str, recurrence_weeks: int) -> str:
    """
    주어진 제목과 시간으로 구글 캘린더에 매주 반복되는 이벤트를 생성합니다.
    Args:
        title (str): 이벤트 제목.
        start_time (str): 시작 시간 ('YYYY-MM-DDTHH:MM:SS' 형식).
        end_time (str): 종료 시간 ('YYYY-MM-DDTHH:MM:SS' 형식).
        recurrence_weeks (int): 이벤트가 반복될 총 주(week) 수.
    """
    print(f"TOOL CALLED: google_calendar_create_recurring_event(title='{title}', weeks={recurrence_weeks})")
    creds = _get_calendar_credentials()
    if not creds: return "Google Calendar 인증에 실패했습니다."

    try:
        service = build("calendar", "v3", credentials=creds)
        event_body = {
            "summary": title,
            "description": "WellnessCoachAI를 통해 생성된 일정입니다.",
            "start": {"dateTime": start_time, "timeZone": "Asia/Seoul"},
            "end": {"dateTime": end_time, "timeZone": "Asia/Seoul"},
            "recurrence": [f'RRULE:FREQ=WEEKLY;COUNT={recurrence_weeks}']
        }
        created_event = service.events().insert(calendarId="primary", body=event_body).execute()
        return f"✅ 구글 캘린더에 '{title}' 일정을 {recurrence_weeks}주 동안 반복되도록 등록했습니다. 링크: {created_event.get('htmlLink', '')}"
    except Exception as e:
        return f"❌ 반복 일정 생성 중 오류 발생: {e}"

def get_weather(location: str) -> str:
    """
    주어진 위치의 현재 날씨 정보를 가져옵니다.
    """
    print(f"TOOL CALLED: get_weather(location='{location}')")
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return "OpenWeatherMap API 키가 설정되지 않았습니다."

    # OpenWeatherMap API URL
    url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&lang=kr&units=metric"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        description = data['weather'][0]['description']
        temp = data['main']['temp']
        feels_like = data['main']['feels_like']
        
        return f"현재 {location}의 날씨는 '{description}'이며, 온도는 {temp}°C, 체감 온도는 {feels_like}°C 입니다."
        
    except Exception as e:
        return f"{location}의 날씨 정보를 가져오는 데 실패했습니다: {e}"


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