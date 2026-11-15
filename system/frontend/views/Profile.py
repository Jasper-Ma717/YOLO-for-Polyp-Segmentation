import streamlit as st
import requests
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, get_auth_headers

ensure_login()

st.title("👤 个人中心")

current_user = st.session_state.get("current_user") or {}
headers = get_auth_headers()

# ========== 基本信息展示 ==========
st.subheader("账户信息")
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**用户名：** {current_user.get('username', '-')}")
    st.markdown(f"**用户 ID：** {current_user.get('id', '-')}")
with col2:
    role_label = "管理员" if current_user.get("role") == "admin" else "医生"
    st.markdown(f"**角色：** {role_label}")
    st.markdown(f"**注册时间：** {str(current_user.get('created_at', '-'))[:10]}")

st.markdown("---")

# ========== 修改密码 ==========
st.subheader("🔒 修改密码")

with st.form("change_password_form"):
    old_password = st.text_input("当前密码", type="password", placeholder="请输入当前密码")
    new_password = st.text_input("新密码", type="password", placeholder="至少6位")
    confirm_password = st.text_input("确认新密码", type="password", placeholder="再次输入新密码")
    st.write("")
    change_btn = st.form_submit_button("确认修改", type="primary", use_container_width=True)

if change_btn:
    if not old_password:
        st.error("请输入当前密码")
    elif len(new_password) < 6:
        st.error("新密码长度必须≥6位")
    elif new_password != confirm_password:
        st.error("两次输入的新密码不一致")
    elif old_password == new_password:
        st.warning("新密码与当前密码相同，无需修改")
    else:
        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/auth/change-password",
                json={"old_password": old_password, "new_password": new_password},
                headers=headers,
                timeout=20,
            )
            if resp.status_code == 200:
                st.success("✅ 密码修改成功！下次登录请使用新密码。")
            else:
                detail = resp.json().get("detail", "修改失败")
                st.error(f"修改失败：{detail}")
        except requests.exceptions.RequestException as exc:
            st.error(f"请求失败: {exc}")
