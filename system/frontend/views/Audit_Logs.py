import streamlit as st
import pandas as pd
import requests
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, get_auth_headers

ensure_login()

current_user = st.session_state.get("current_user") or {}
if current_user.get("role") != "admin":
    st.warning("仅管理员可访问审计日志页面。")
    st.stop()

st.title("🧾 系统审计日志")
st.caption("查看关键业务操作轨迹，包括登录、检测、患者维护和角色调整。")

action_filter = st.selectbox(
    "按操作类型筛选",
    ["全部", "login", "register", "change_password", "create_patient", "update_patient", "delete_patient", "detect_image", "detect_video", "update_history", "delete_history", "update_user_role", "delete_user", "export_patient_report"],
)
limit = st.slider("读取条数", min_value=20, max_value=300, value=100, step=20)

params = {"limit": limit}
if action_filter != "全部":
    params["action"] = action_filter

try:
    resp = requests.get(f"{BACKEND_URL}/api/audit/logs", headers=get_auth_headers(), params=params, timeout=20)
except requests.exceptions.RequestException as exc:
    st.error(f"获取审计日志失败: {exc}")
    st.stop()

if resp.status_code != 200:
    st.error(resp.text)
    st.stop()

logs = resp.json().get("data", [])
if not logs:
    st.info("暂无审计日志。")
    st.stop()

df = pd.DataFrame(logs)
st.download_button(
    label="⬇️ 导出审计日志 CSV",
    data=df.to_csv(index=False).encode("utf-8-sig"),
    file_name="audit_logs.csv",
    mime="text/csv",
)

st.dataframe(df, use_container_width=True)
