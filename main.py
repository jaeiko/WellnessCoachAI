import time
from dotenv import load_dotenv
import os
import re
import regex
import json
import sys
import io
load_dotenv()

# Windows 터미널에서 한글이 깨지지 않도록 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core import exceptions as api_core_exceptions

import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. Firebase 초기화 ---
try:
    cred = credentials.Certificate("wellnesscoachai-firebase-adminsdk.json") # 다운로드한 키 파일 이름으로 변경
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


# --- 5. API 호출 및 JSON 추출 함수 ---
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

        if not past_reports:
            print("분석할 과거 데이터가 없습니다.")
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

# --- 최종 실행 로직 ---
if __name__ == "__main__":
    # --- (수정) 1단계: 샘플 데이터 파일에서 로드 ---
    try:
        with open("data/sample_data.json", "r", encoding="utf-8") as f:
            sample_data = json.load(f)
    except FileNotFoundError:
        print("오류: data/sample_data.json 파일을 찾을 수 없습니다.")
        exit()
    
    # --- 2단계: 사용자 목표 입력 및 진단 프롬프트 실행 ---
    print("="*20 + "\n1단계: 건강 데이터 분석 시작\n" + "="*20)
    
    user_goal = input("이번 주의 건강 목표를 입력해주세요 (예: 스트레스 관리): ")
    
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
        save_analysis_to_db("test_user_01", analysis_result_json) 
    else:
        print("1단계: 진단 분석에 실패했습니다. 원본 답변:", analysis_response_text)
        exit()

    # --- 3단계: 상호작용 (사용자 피드백 입력) ---
    print("\n" + "="*20 + "\n상호작용: 사용자에게 질문\n" + "="*20)
    user_explanation = analysis_result_json.get("key_events", [{}])[0].get("explanation_for_user", "분석 중 오류가 발생했습니다.")
    print(f"AI 비서: {user_explanation}")
    
    user_feedback = input("당신의 답변을 입력해주세요: ")
    print("-" * 20)

    # --- 4단계: 루틴 제안 프롬프트 실행 ---
    print("\n" + "="*20 + "\n4단계: 맞춤형 루틴 제안 시작\n" + "="*20)
    
    prompt_2 = f"""
{ROUTINE_SUGGESTION_PROMPT}

---
analysis_result: {json.dumps(analysis_result_json)}
user_preferences: {json.dumps(sample_data.get("user_preferences"))}
user_feedback: "{user_feedback}" 
"""
    
    routine_response_text = ask_question_to_gemini_cache(prompt_2) 
    routine_result_json = json_match(routine_response_text)
    
    print("\n--- 4단계: 루틴 제안 결과 (JSON) ---\n")
    if routine_result_json:
        print(json.dumps(routine_result_json, indent=2, ensure_ascii=False))
    else:
        print("4단계: 루틴 제안에 실패했습니다. 원본 답변:", routine_response_text)

    # --- 5단계: 장기 패턴 분석 실행 ---
    analyze_long_term_patterns("test_user_01")