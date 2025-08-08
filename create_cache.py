# create_cache.py
import google.generativeai as genai
import os
from dotenv import load_dotenv
import pathlib

# .env 파일 로드 및 API 키 설정
print("API 키를 설정합니다...")
load_dotenv(dotenv_path="multi_tool_agent/.env")
genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))

# docs 폴더에 있는 모든 PDF 파일 경로 찾기
pdf_files = [str(p) for p in pathlib.Path("docs").glob("*.pdf")]
print(f"다음 파일들을 캐싱합니다: {pdf_files}")

# 파일 업로드 및 캐시 생성
print("파일을 업로드하고 캐시를 생성하는 중입니다... (시간이 걸릴 수 있습니다)")
cache = genai.caching.CachedContent.create(
    model="models/gemini-2.0-flash", # Agent가 사용하는 모델과 동일해야 함
    display_name="wellness_knowledge_base",
    contents=[genai.upload_file(path) for path in pdf_files]
)
print("✅ 캐시 생성을 완료했습니다!")

# 생성된 '도서관 카드'(캐시 이름) 출력
print("\n--- 중요 ---")
print(f"생성된 캐시 이름: {cache.name}")
print("이 이름을 복사하여 .env 파일에 GEMINI_CACHE_NAME으로 저장하세요.")