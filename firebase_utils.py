# firebase_utils.py

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

def initialize_firebase():
    """
    Firebase 앱을 초기화하고 Firestore 클라이언트를 반환합니다.
    이미 초기화된 경우, 기존 앱을 사용합니다.
    """
    try:
        # 앱이 이미 초기화되었는지 확인
        firebase_admin.get_app()
    except ValueError:
        # 초기화되지 않았다면, 서비스 계정 키를 사용하여 초기화
        cred = credentials.Certificate("firebase_credentials.json")
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def save_analysis_json(db, user_id: str, session_id: str, analysis_data: dict):
    """
    구조화된 JSON 분석 결과를 Firestore에 저장합니다.
    """
    # 문서 ID를 타임스탬프로 하여 시간순 정렬이 용이하게 함
    doc_id = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    doc_ref = db.collection('users').document(user_id).collection('analysis_history').document(doc_id)
    
    analysis_data['timestamp'] = firestore.SERVER_TIMESTAMP
    doc_ref.set(analysis_data)
    print(f"✅ Firestore에 분석 결과 저장 완료: {user_id}/{doc_id}")

def get_user_profile(db, user_id: str) -> dict | None:
    """
    Firestore에서 사용자 프로필 정보를 가져옵니다. 없으면 None을 반환합니다.
    """
    doc_ref = db.collection('users').document(user_id)
    doc = doc_ref.get()
    if doc.exists and doc.to_dict().get('profile'):
        return doc.to_dict()['profile']
    else:
        # 🔽 프로필이 없으면 None을 반환
        return None