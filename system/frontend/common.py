import requests
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"


def get_auth_headers():
    token = st.session_state.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def ensure_login():
    if not st.session_state.get("access_token"):
        st.warning("请先在主页登录后再访问此页面。")
        st.stop()


def fetch_patients():
    headers = get_auth_headers()
    if not headers:
        return []

    try:
        resp = requests.get(f"{BACKEND_URL}/api/patients/mine", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return data.get("data", [])
    except requests.exceptions.RequestException:
        return []
    return []


def init_session_state():
    if "access_token" not in st.session_state:
        st.session_state.access_token = None
    if "current_user" not in st.session_state:
        st.session_state.current_user = None

def handle_logout():
    st.session_state.access_token = None
    st.session_state.current_user = None
    st.rerun()

def require_login():
    ensure_login()
