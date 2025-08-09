# main.py

# 1. .env 파일을 가장 먼저 로드하여 환경 변수를 설정합니다.
import json
from firebase_utils import initialize_firebase, save_analysis_json
import io
import sys
from google.genai import types
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
import asyncio
import os
import google.generativeai as genai
from multi_tool_agent.tools import get_health_data
from multi_tool_agent.agent import wellness_coach_agent
from dotenv import load_dotenv
load_dotenv(dotenv_path="multi_tool_agent/.env")

# 2. .env가 로드된 후에 나머지 모듈들을 안전하게 불러옵니다.

# Windows 터미널에서 한글이 깨지지 않도록 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# API 키 설정
genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))


# --- 대화 매니저 클래스 ---
# main.py

class ConversationManager:
    def __init__(self, agent):
        self.agent = agent
        self.runner = None
        self.db = initialize_firebase()
        self.session_info = {
            "app_name": "wellness_coach_app",
            "user_id": "user_1",
            "session_id": "session_1"
        }

    async def initialize(self):
        """세션과 러너를 비동기적으로 초기화합니다."""
        session_service = InMemorySessionService()
        await session_service.create_session(**self.session_info)
        self.runner = Runner(
            agent=self.agent,
            app_name=self.session_info["app_name"],
            session_service=session_service
        )
        print("🤖 Wellness Coach AI가 초기화되었습니다.")

    async def send_message(self, query):
        """사용자 메시지를 보내고 전체 답변을 받아옵니다."""
        print(f"\n> 당신: {query}")
        content = types.Content(role='user', parts=[types.Part(text=query)])

        final_response_text = None
        async for event in self.runner.run_async(user_id=self.session_info["user_id"], session_id=self.session_info["session_id"], new_message=content):
            if event.is_final_response():
                final_response_text = event.content.parts[0].text
                break

        if final_response_text:
            clean_text = final_response_text.strip()
            # 이제 모든 응답은 텍스트이거나, 분석 결과를 담은 JSON일 수 있습니다.
            try:
                # 응답이 JSON 형식인지 시도해 봅니다.
                response_data = json.loads(clean_text)
                analysis_json = response_data.get("analysis_json", {})
                response_for_user = response_data.get(
                    "response_for_user", "오류: 응답을 해석할 수 없습니다.")

                print(f"\nAI 비서: {response_for_user}")

                if analysis_json:
                    save_analysis_json(
                        db=self.db,
                        user_id=self.session_info["user_id"],
                        session_id=self.session_info["session_id"],
                        analysis_data=analysis_json
                    )
            except json.JSONDecodeError:
                # JSON 파싱에 실패하면, 일반 텍스트 답변으로 간주하고 그대로 출력합니다.
                print(f"\nAI 비서: {clean_text}")
        else:
            print("\nAI 비서: 죄송합니다, 답변을 생성하는 데 실패했습니다.")


async def main():
    manager = ConversationManager(agent=wellness_coach_agent)
    await manager.initialize()
    await manager.send_message(input("AI에게 먼저 분석을 시작하도록 지시하세요: "))
    while True:
        user_input = input("\n> ")
        if user_input.lower() in ["종료", "끝", "exit"]:
            break
        await manager.send_message(user_input)
    print("\n대화를 종료합니다.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 종료되었습니다.")
