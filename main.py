# main.py
from multi_tool_agent.agent import wellness_coach_agent
from dotenv import load_dotenv
import google.generativeai as genai
import os
import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import sys
import io
from firebase_utils import initialize_firebase, save_analysis_json
import json

# Windows 터미널에서 한글이 깨지지 않도록 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# multi_tool_agent 폴더의 agent.py에서 '만능 에이전트'를 가져옵니다.

# .env 파일 로드 및 API 키 설정
load_dotenv(dotenv_path="multi_tool_agent/.env")
genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))


# --- 대화 매니저 클래스 ---
class ConversationManager:
    def __init__(self, agent):
        self.agent = agent
        self.runner = None
        self.session_info = {
            "app_name": "wellness_coach_app",
            "user_id": "user_1",
            "session_id": "session_1"
        }
        self.db = initialize_firebase()

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

    def format_response(self, response):
        """AI의 답변에서 텍스트와 도구 사용 내역을 모두 추출하여 예쁘게 만듭니다."""

        # 1. 텍스트 부분 추출 (새로운 방식)
        text_part = ""
        if response and response.parts:
            text_part = response.parts[0].text

        # 2. 도구 사용(function_call) 부분 추출
        tool_calls_part = ""
        try:
            if response and response.parts:
                for part in response.parts:
                    if part.function_call:
                        tool_name = part.function_call.name.split('/')[-1]
                        args = dict(part.function_call.args)
                        tool_calls_part += f"\n\n🔧 **도구 사용:** `{tool_name}`"
        except Exception:
            pass

        return text_part + tool_calls_part

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
            try:
                # 🔽 [핵심 수정] AI의 응답에서 Markdown 코드 블록을 제거합니다.
                clean_text = final_response_text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:].strip() # "```json" 과 줄바꿈 제거
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3].strip()
                
                response_data = json.loads(clean_text)
                analysis_json = response_data.get("analysis_json", {})
                response_for_user = response_data.get("response_for_user", "오류: 응답을 해석할 수 없습니다.")

                print(f"\nAI 비서: {response_for_user}")
                
                # Firestore 저장 로직은 그대로 유지
                if analysis_json: # analysis_json이 비어있지 않을 때만 저장
                    save_analysis_json(
                        db=self.db,
                        user_id=self.session_info["user_id"],
                        session_id=self.session_info["session_id"],
                        analysis_data=analysis_json 
                    )

            except json.JSONDecodeError:
                # 파싱 실패 시, 원본 텍스트라도 보여줌
                print(f"\nAI 비서: {final_response_text}")
                print("(경고: AI 응답을 JSON 형식으로 파싱하는 데 실패했습니다.)")
        else:
            print("\nAI 비서: 죄송합니다, 답변을 생성하는 데 실패했습니다.")


async def main():
    """메인 실행 함수"""

    # 대화 매니저 생성 및 초기화
    manager = ConversationManager(agent=wellness_coach_agent)
    await manager.initialize()

    # AI에게 먼저 분석을 시작하도록 지시
    await manager.send_message(input("AI에게 먼저 분석을 시작하도록 지시하세요: "))

    while True:
        user_input = input("\n> ")
        if user_input.lower() in ["종료", "끝", "exit"]:
            break
        await manager.send_message(user_input)

    print("\n대화를 종료합니다.")


# --- 최종 실행 ---
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 종료되었습니다.")
