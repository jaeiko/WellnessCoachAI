# multi_tool_agent/agent.py
from google.adk.agents import Agent

# 같은 폴더에 있는 tools.py에서 모든 도구들을 가져옵니다.
from .tools import get_health_data, Youtube, google_calendar_create_event, get_weather, find_nearby_places

# --- 프롬프트 파일 읽기 ---
try:
    with open("prompts/analytics_prompt.txt", "r", encoding="utf-8") as f:
        # analytics_prompt는 이제 get_health_data 도구에 대한 상세 지침이 됩니다.
        HEALTHCARE_ANALYTICS_INSTRUCTIONS = f.read()
except FileNotFoundError:
    HEALTHCARE_ANALYTICS_INSTRUCTIONS = "Analyze health data."  # 기본값

# --- (신규) 병원 추천 전문 에이전트 ---
healthcare_locator_agent = Agent(
    name="HealthcareLocatorAgent",
    model="gemini-1.5-flash",
    description="Finds nearby clinics, hospitals, or counseling centers based on user's needs.",
    instruction="""
You are an assistant that helps users find nearby healthcare facilities.
Use the 'find_nearby_places' tool to search for clinics based on the user's request.
Provide the search results to the user.
""",
    tools=[
        find_nearby_places
    ]
)

# --- '만능' 웰니스 코치 에이전트 ---
wellness_coach_agent = Agent(
    name="WellnessCoachAgent",
    model="gemini-1.5-flash",
    description="A comprehensive AI wellness coach that analyzes health data and suggests routines.",
    instruction="""
HEALTHCARE_ANALYTICS_INSTRUCTIONS
""",
    # 모든 도구를 이 하나의 에이전트에게 줍니다.
    tools=[get_health_data, Youtube, google_calendar_create_event, get_weather,],
    sub_agents=[
        healthcare_locator_agent
    ]
)
