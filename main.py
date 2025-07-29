import time
from dotenv import load_dotenv
import os
import re
import regex
import json
load_dotenv()

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as api_core_exceptions

import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. Firebase 초기화 ---
try:
    # 다운로드한 Firebase 키 파일의 실제 이름으로 변경해야 합니다.
    cred = credentials.Certificate("wellnesscoachai-firebase-adminsdk.json")
    # 이미 초기화되었는지 확인
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Firebase 초기화 오류: {e}")
    print("Firebase 키 파일을 확인해주세요. DB 기능 없이 계속합니다.")
    db = None

# --- 2. 프롬프트 파일 읽기 ---
try:
    with open("prompts/analytics_prompt.txt", "r", encoding="utf-8") as f:
        HEALTHCARE_ANALYTICS_PROMPT = f.read()
    with open("prompts/suggestion_prompt.txt", "r", encoding="utf-8") as f:
        ROUTINE_SUGGESTION_PROMPT = f.read()
    with open("prompts/long_term_analysis_prompt.txt", "r", encoding="utf-8") as f:
        LONG_TERM_ANALYSIS_PROMPT = f.read()
except FileNotFoundError as e:
    print(f"오류: '{e.filename}' 프롬프트 파일을 찾을 수 없습니다. 'prompts' 폴더를 확인해주세요.")
    exit()

# --- 3. Gemini API 클라이언트 설정 ---
model_name = "gemini-1.5-flash"
genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))
model = genai.GenerativeModel(model_name)

# --- 4. 로컬 PDF 파일 업로드 ---
pdf_file_paths = [
    "docs/Introduction to stress management.pdf",
    "docs/The science of sleep.pdf",
    "docs/Stress Management-textbook.pdf",
    "docs/불면증의 인지행동치료.pdf",
    "docs/Breathing Techniques for the Nervous System.pdf",
    "docs/The Mind-Body Connection.pdf",
    "docs/Physiology-of-Exercise.pdf",
    "docs/Food, Nutrition, Health and Fitness.pdf",
]

print("PDF 파일을 업로드하는 중...")
attachments = []
for path in pdf_file_paths:
    try:
        uploaded_file = genai.upload_file(path=path)
        attachments.append(uploaded_file)
        print(f"'{path}' 업로드 성공.")
    except Exception as e:
        print(f"'{path}' 파일 업로드 실패: {e}")
print("-" * 20)

# --- 5. 샘플 데이터 정의 ---
# 실제로는 이 데이터를 안드로이드 앱에서 받아오게 됩니다.
SAMPLE_TIMESERIES_DATA = '[{"time": "2025-07-27T22:00:00Z", "heart_rate": 65, "stress": 15}, {"time": "2025-07-28T03:00:00Z", "heart_rate": 95, "stress": 70}, {"time": "2025-07-28T09:00:00Z", "heart_rate": 80, "stress": 30}]'
SAMPLE_SLEEP_DATA = '{"total_sleep_time_minutes": 360, "deep_sleep_minutes": 50, "rem_sleep_minutes": 70, "awake_minutes": 30}'
SAMPLE_EXERCISE_DATA = '[]'
SAMPLE_USER_PREFERENCES = '{"likes": ["음악 듣기", "산책"], "dislikes": ["아침 일찍 일어나기"]}'

# --- 6. API 호출 및 JSON 추출 함수 ---
def ask_question_to_gemini_cache(prompt, attachments=None, max_retries=5, retry_delay=5):
    start_time = time.time()
    if attachments:
        contents = attachments + [prompt]
    else: 
        contents = [prompt]
    
    generation_config = GenerationConfig(
        temperature=0.3,
        response_mime_type="application/json"
    )

    for attempt in range(max_retries):
        try:
            print(f"attempt {attempt + 1} starting at {time.time() - start_time:.2f}s")
            api_start = time.time()
            response = model.generate_content(
                contents=contents,
                generation_config=generation_config
            )
            print(f"API call took {time.time() - api_start:.2f}s")
            return response.text
        except api_core_exceptions.GoogleAPICallError as e:
            print(f"Google API 오류 발생 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"{retry_delay}초 후 재시도합니다...")
                time.sleep(retry_delay)
            else:
                print("최대 재시도 횟수를 초과했습니다.")
                raise
        except Exception as e:
            print(f"예상치 못한 오류 발생 (시도 {attempt + 1}/{max_retries}): {e}")
            raise
    return None

def json_match(input_string):
    if not input_string: return None
    input_string = re.sub(r"```json\s*|\s*```", "", input_string.strip())
    try:
        return json.loads(input_string)
    except json.JSONDecodeError:
        return None
    
def save_analysis_to_db(user_id, analysis_data):
    if db is None:
        print("DB가 초기화되지 않아 저장을 건너뜁니다.")
        return
    try:
        doc_ref = db.collection("health_analyses").document(user_id).collection("daily_reports").document()
        doc_ref.set(analysis_data)
        print(f"분석 결과를 DB에 성공적으로 저장했습니다.")
    except Exception as e:
        print(f"DB 저장 중 오류 발생: {e}")

def analyze_long_term_patterns(user_id):
    if db is None:
        print("DB가 초기화되지 않아 장기 분석을 건너뜁니다.")
        return
        
    print("\n" + "="*20 + "\n장기 패턴 분석 시작\n" + "="*20)
    
    try:
        reports_ref = db.collection("health_analyses").document(user_id).collection("daily_reports")
        docs = reports_ref.stream()
        past_reports = [doc.to_dict() for doc in docs]

        if len(past_reports) < 2:
            print("분석할 과거 데이터가 충분하지 않습니다 (최소 2개 필요).")
            return

        prompt_3 = f"""
{LONG_TERM_ANALYSIS_PROMPT}

---
past_reports: {json.dumps(past_reports)}
"""
        
        long_term_response_text = ask_question_to_gemini_cache(prompt_3)
        long_term_result_json = json_match(long_term_response_text)

        print("\n--- 장기 분석 결과 (JSON) ---\n")
        if long_term_result_json:
            print(json.dumps(long_term_result_json, indent=2, ensure_ascii=False))
        else:
            print("장기 분석에 실패했습니다. 원본 답변:", long_term_response_text)
    except Exception as e:
        print(f"장기 분석 중 오류 발생: {e}")

# --- 최종 실행 로직 (대화 루프 적용) ---
if __name__ == "__main__":
    USER_ID = "test_user_01" # 사용자 ID

    while True: # 대화를 계속하기 위한 무한 루프 시작
        # --- 1단계: 사용자 목표 입력 및 진단 프롬프트 실행 ---
        print("\n" + "="*20 + "\n1단계: 건강 데이터 분석 시작\n" + "="*20)
        
        user_goal = input("이번 주의 건강 목표를 입력해주세요 (종료하려면 '종료' 입력): ")
        
        # 사용자가 종료를 원하면 루프 탈출
        if user_goal.lower() in ["종료", "끝", "exit"]:
            break

        # --- (수정) 샘플 데이터 로드 위치를 루프 안으로 이동 ---
        try:
            with open("data/sample_data.json", "r", encoding="utf-8") as f:
                sample_data = json.load(f)
        except FileNotFoundError:
            print("오류: data/sample_data.json 파일을 찾을 수 없습니다.")
            continue # 루프의 처음으로 돌아감
            
        prompt_1 = f"""
{HEALTHCARE_ANALYTICS_PROMPT}

---
user_goal: "{user_goal}"
timeseries_data: {json.dumps(sample_data.get("timeseries_data"))}
sleep_data: {json.dumps(sample_data.get("sleep_data"))}
exercise_data: {json.dumps(sample_data.get("exercise_data"))}
"""
        
        analysis_response_text = ask_question_to_gemini_cache(prompt_1, attachments)
        analysis_result_json = json_match(analysis_response_text)
        
        print("\n--- 1단계: 진단 결과 (JSON) ---\n")
        if analysis_result_json:
            print(json.dumps(analysis_result_json, indent=2, ensure_ascii=False))
            save_analysis_to_db(USER_ID, analysis_result_json) 
        else:
            print("1단계: 진단 분석에 실패했습니다. 원본 답변:", analysis_response_text)
            continue # 실패 시 루프의 처음으로 돌아감

        # --- 2단계: 상호작용 (사용자 피드백 입력) ---
        key_events_list = analysis_result_json.get("key_events", [])
        
        if not key_events_list:
            print("\n" + "="*20 + "\nAI 비서: 분석 결과, 특별한 이상 징후 없이 건강한 상태를 잘 유지하고 계시네요! 멋집니다.\n" + "="*20)
        else:
            print("\n" + "="*20 + "\n2단계: 상호작용: 사용자에게 질문\n" + "="*20)
            user_explanation = key_events_list[0].get("explanation_for_user", "분석 중 오류가 발생했습니다.")
            print(f"AI 비서: {user_explanation}")
            
            user_feedback = input("당신의 답변을 입력해주세요: ")
            print("-" * 20)

            # --- 3단계: 루틴 제안 프롬프트 실행 ---
            print("\n" + "="*20 + "\n3단계: 맞춤형 루틴 제안 시작\n" + "="*20)
            
            prompt_2 = f"""
{ROUTINE_SUGGESTION_PROMPT}

---
analysis_result: {json.dumps(analysis_result_json)}
user_preferences: {json.dumps(sample_data.get("user_preferences"))}
user_feedback: "{user_feedback}" 
"""
            
            routine_response_text = ask_question_to_gemini_cache(prompt_2) 
            routine_result_json = json_match(routine_response_text)
            
            print("\n--- 3단계: 루틴 제안 결과 (JSON) ---\n")
            if routine_result_json:
                print(json.dumps(routine_result_json, indent=2, ensure_ascii=False))
            else:
                print("3단계: 루틴 제안에 실패했습니다. 원본 답변:", routine_response_text)

        # --- 대화 계속 여부 확인 ---
        continue_chat = input("\n더 분석하고 싶은 내용이 있으신가요? (계속하려면 Enter, 끝내려면 '종료' 입력): ")
        if continue_chat.lower() in ["종료", "끝", "exit"]:
            break

    # --- 4단계: 장기 패턴 분석 실행 (루프 종료 후 1회 실행) ---
    analyze_long_term_patterns(USER_ID)

    print("\nAI 비서와의 대화를 종료합니다. 건강한 하루 보내세요!")