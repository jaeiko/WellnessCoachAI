import json
import os
import requests
import datetime
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from firebase_utils import initialize_firebase, get_user_profile
from googleapiclient.errors import HttpError
from typing import Optional
from google.generativeai.caching import CachedContent
import google.generativeai as genai
from firebase_admin import firestore
import dateparser

# 구글 캘린더 API가 허용할 권한 범위
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# 🔽 [핵심 추가 1] 캐시 객체를 파일 상단에서 미리 로드합니다.
CACHE_NAME = os.getenv("GEMINI_CACHE_NAME")
if not CACHE_NAME:
    raise ValueError("GEMINI_CACHE_NAME이 .env 파일에 설정되지 않았습니다.")
print(f"'{CACHE_NAME}' 캐시를 로드합니다...")
KNOWLEDGE_CACHE = CachedContent.get(name=CACHE_NAME)
print("✅ 캐시 로드 완료!")


def get_health_data() -> str:
    """
    사용자의 건강 데이터를 가져옵니다. 
    1. Firestore에서 프로필 조회 -> 2. 실패 시 로컬 파일 조회 -> 3. 모두 실패 시 오류 반환
    """
    print("TOOL CALLED: get_health_data()")
    
    # 1. DB에서 프로필을 먼저 시도합니다.
    db = initialize_firebase()
    user_profile = get_user_profile(db, "user_1") 
    
    # 2. DB에 프로필이 있는 경우 (성공!)
    if user_profile:
        print("INFO: Firestore에서 사용자 프로필을 성공적으로 가져왔습니다.")
        try:
            # 나머지 데이터는 로컬 파일에서 가져와 결합합니다.
            with open("data/sample_data.json", "r", encoding="utf-8") as f:
                health_data = json.load(f)
                health_data['user_profile'] = user_profile 
                return json.dumps(health_data, ensure_ascii=False)
        except FileNotFoundError:
            # 로컬 파일이 없어도 프로필만으로 응답할 수 있도록 구성
            return json.dumps({"user_profile": user_profile}, ensure_ascii=False)

    # 3. DB에 프로필이 없는 경우 (대체 방안 시도)
    else:
        print("WARNING: Firestore에 프로필이 없어 로컬 sample_data.json을 사용합니다.")
        try:
            # 로컬 샘플 데이터 전체를 사용합니다.
            with open("data/sample_data.json", "r", encoding="utf-8") as f:
                health_data = json.load(f)
                return json.dumps(health_data, ensure_ascii=False)
        except FileNotFoundError:
            # 4. 로컬 파일도 없는 경우 (최종 실패)
            print("ERROR: DB와 로컬에서 모두 사용자 데이터를 찾을 수 없습니다.")
            return json.dumps({"error": "DB와 로컬 파일 모두에 사용자 데이터가 존재하지 않습니다."})


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

def convert_natural_time_to_iso(time_expression: str) -> str:
    """
    "오늘 저녁 7시 30분", "모레 20:15"과 같은 자연어 시간 표현을
    'YYYY-MM-DDTHH:MM:SS' 형식의 ISO 문자열로 변환합니다.
    """
    print(f"TOOL CALLED: convert_natural_time_to_iso(expression='{time_expression}')")
    try:
        # 🔽 [핵심 수정 1] "오늘"의 기준이 될 현재 시간을 가져옵니다.
        now = datetime.datetime.now()

        # 🔽 [핵심 수정 2] settings에 'RELATIVE_BASE'를 추가하여 기준점을 명시합니다.
        parsed_time = dateparser.parse(
            time_expression,
            languages=['ko'],
            settings={'PREFER_DATES_FROM': 'future', 'TIMEZONE': 'Asia/Seoul', 'RELATIVE_BASE': now}
        )
        if parsed_time:
            return parsed_time.strftime('%Y-%m-%dT%H:%M:%S')
        else:
            return f"오류: '{time_expression}'을(를) 시간으로 해석할 수 없습니다."
    except Exception as e:
        return f"시간 변환 중 오류 발생: {e}"

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
    
def get_past_analysis_logs(user_id: str, days: int) -> str:
    """
    지정된 기간 동안의 과거 건강 분석 기록을 Firestore에서 가져옵니다.
    
    Args:
        user_id (str): 조회할 사용자의 ID.
        days (int): 오늘로부터 며칠 전까지의 기록을 조회할지 지정 (예: 7).
    """
    print(f"TOOL CALLED: get_past_analysis_logs(user_id='{user_id}', days={days})")
    try:
        db = initialize_firebase()
        
        # 'analysis_history' 컬렉션에서 문서를 시간순으로 정렬하여 가져옴
        logs_ref = db.collection('users').document(user_id).collection('analysis_history').order_by(
            'timestamp', direction=firestore.Query.DESCENDING
        ).limit(days) # 간단하게 최근 days개의 문서를 가져옴 (정확한 날짜 필터링은 로직 추가 필요)
        
        docs = logs_ref.stream()
        
        past_logs = []
        for doc in docs:
            log_data = doc.to_dict()
            # Firestore의 Timestamp 객체를 문자열로 변환
            if 'timestamp' in log_data and hasattr(log_data['timestamp'], 'isoformat'):
                log_data['timestamp'] = log_data['timestamp'].isoformat()
            past_logs.append(log_data)

        if not past_logs:
            return "저장된 과거 분석 기록이 없습니다."
            
        # Agent가 처리하기 쉽도록 JSON 문자열로 변환하여 반환
        return json.dumps(past_logs, ensure_ascii=False)

    except Exception as e:
        return f"과거 기록 조회 중 오류가 발생했습니다: {e}"
    
    
# 캐시를 사용하는 새로운 도구 함수를 정의
def ask_knowledge_base(question: str) -> str:
    """
    PDF 문서들이 캐싱된 지식 베이스에 특정 질문을 하여 답변을 얻습니다.
    분석 중 과학적 근거를 찾을 때 사용합니다.
    Args:
        question (str): 지식 베이스에 물어볼 구체적인 질문.
    """
    print(f"TOOL CALLED: ask_knowledge_base(question='{question}')")
    try:
        # 캐시를 사용하여 모델을 초기화합니다.
        model = genai.GenerativeModel.from_cached_content(cached_content=KNOWLEDGE_CACHE)
        
        # 캐싱된 문서 내용을 바탕으로 질문에 대한 답변을 생성합니다.
        response = model.generate_content(question)
        
        return response.text
    except Exception as e:
        return f"지식 베이스 조회 중 오류가 발생했습니다: {e}"