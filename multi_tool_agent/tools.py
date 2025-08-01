import json

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
    (현재는 생성할 이벤트 정보를 출력하는 것으로 시뮬레이션합니다.)
    """
    print(f"TOOL CALLED: google_calendar_create_event()")
    return f"구글 캘린더에 '{title}'라는 이름의 일정을 성공적으로 등록했습니다 (시뮬레이션)."