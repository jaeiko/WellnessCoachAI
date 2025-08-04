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

# --- '만능' 웰니스 코치 에이전트 ---
wellness_coach_agent = Agent(
    name="WellnessCoachAgent",
    model="gemini-1.5-flash",
    description="A comprehensive AI wellness coach that analyzes health data, suggests routines, and finds nearby places.",
    instruction=HEALTHCARE_ANALYTICS_INSTRUCTIONS, # instruction에 읽어온 프롬프트를 직접 전달
    
    # ⭐ 모든 도구를 이 하나의 에이전트에게 줍니다.
    tools=[
        get_health_data, 
        Youtube, 
        google_calendar_create_event, 
        get_weather,
        find_nearby_places # find_nearby_places를 여기에 포함
    ],
)