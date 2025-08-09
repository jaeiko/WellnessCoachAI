# multi_tool_agent/agent.py
from google.adk.agents import Agent
import google.generativeai as genai
import os

# 같은 폴더에 있는 tools.py에서 모든 도구들을 가져옵니다.
from .tools import get_health_data, Youtube, google_calendar_create_single_event, google_calendar_create_recurring_event, get_weather, find_nearby_places, search_naver_news, ask_knowledge_base, convert_natural_time_to_iso

# --- Prompt ---
try:
    with open("prompts/analytics_prompt.txt", "r", encoding="utf-8") as f:
        HEALTHCARE_ANALYTICS_INSTRUCTIONS = f.read()
except FileNotFoundError:
    HEALTHCARE_ANALYTICS_INSTRUCTIONS = "Analyze health data."

# try:
#     with open("prompts/suggestion_prompt.txt", "r", encoding="utf-8") as f:
#         HEALTHCARE_SUGGESTION_INSTRUCTIONS = f.read()
# except FileNotFoundError:
#     HEALTHCARE_SUGGESTION_INSTRUCTIONS = "Suggest wellness routines based on health data."

# try:
#     with open("prompts/long_term_analytics_prompt.txt", "r", encoding="utf-8") as f:
#         LONG_TERM_ANALYTICS_INSTRUCTIONS = f.read()
# except FileNotFoundError:
#     LONG_TERM_ANALYTICS_INSTRUCTIONS = "Suggest long-term wellness routines based on health data."


# --- '만능' 웰니스 코치 에이전트 ---
wellness_coach_agent = Agent(
    name="WellnessCoachAgent",
    model="gemini-2.0-flash",
    description="A comprehensive AI wellness coach that analyzes health data, suggests routines, and finds nearby places.",
    instruction=HEALTHCARE_ANALYTICS_INSTRUCTIONS,  # instruction에 읽어온 프롬프트를 직접 전달

    # ⭐ 모든 도구를 이 하나의 에이전트에게 줍니다.
    tools=[
        get_health_data,
        Youtube,
        google_calendar_create_single_event,  # 🔽 단일 이벤트 도구 추가
        google_calendar_create_recurring_event,
        get_weather,
        find_nearby_places,  # find_nearby_places를 여기에 포함
        ask_knowledge_base,
        convert_natural_time_to_iso,
        search_naver_news
    ],
)
