import streamlit as st
import pandas as pd
import requests
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from common import BACKEND_URL, ensure_login, get_auth_headers

st.set_page_config(page_title="用户管理", page_icon="🛡️", layout="wide")
ensure_login()

st.title("🛡️ 用户管理")
current_user = st.session_state.get("current_user") or {}
if current_user.get("role") != "admin":
    st.warning("仅管理员可访问该页面。")
    st.stop()

headers = get_auth_headers()


def load_users(keyword: str = "", role: str = "全部"):
    params = {}
    if keyword.strip():
        params["keyword"] = keyword.strip()
    if role in {"physician", "admin"}:
        params["role"] = role

    try:
        resp = requests.get(f"{BACKEND_URL}/api/admin/users", headers=headers, params=params, timeout=20)
    except requests.exceptions.RequestException as exc:
        st.error(f"请求失败: {exc}")
        return []

    if resp.status_code != 200:
        st.error(f"拉取用户列表失败: {resp.text}")
        return []

    return resp.json().get("data", [])


st.subheader("查找用户")
keyword = st.text_input("用户名关键词", value=st.session_state.get("admin_user_keyword", ""), placeholder="输入用户名的一部分即可")
role_filter = st.selectbox(
    "角色筛选",
    ["全部", "physician", "admin"],
    index=["全部", "physician", "admin"].index(st.session_state.get("admin_user_role_filter", "全部")),
)
st.session_state.admin_user_keyword = keyword
st.session_state.admin_user_role_filter = role_filter

with st.expander("➕ 新增用户", expanded=False):
    with st.form("create_user_form"):
        new_username = st.text_input("用户名", placeholder="至少3个字符")
        new_password = st.text_input("初始密码", type="password", placeholder="至少6位")
        new_role = st.selectbox("角色", ["physician", "admin"])
        submit_create = st.form_submit_button("创建用户", type="primary")

    if submit_create:
        payload = {"username": new_username.strip(), "password": new_password, "role": new_role}
        if not payload["username"]:
            st.error("用户名不能为空")
        else:
            try:
                create_resp = requests.post(f"{BACKEND_URL}/api/admin/users", json=payload, headers=headers, timeout=20)
                if create_resp.status_code == 200:
                    st.success("用户创建成功")
                    st.rerun()
                else:
                    st.error(f"创建失败: {create_resp.text}")
            except requests.exceptions.RequestException as exc:
                st.error(f"请求失败: {exc}")

users = load_users(keyword, role_filter)
if not users:
    st.info("暂无匹配用户")
    st.stop()

st.subheader("用户列表")
df = pd.DataFrame(users)
show_df = df.rename(columns={"id": "用户ID", "username": "用户名", "role": "角色", "created_at": "创建时间"})
st.dataframe(show_df, use_container_width=True)

st.subheader("用户维护")
user_options = {f"#{u['id']} - {u['username']} ({u['role']})": u for u in users}
selected_user_label = st.selectbox("选择用户", list(user_options.keys()))
selected_user = user_options[selected_user_label]

action_col1, action_col2 = st.columns(2)
with action_col1:
    st.markdown("#### 角色调整")
    role_index = ["physician", "admin"].index(selected_user["role"]) if selected_user["role"] in ["physician", "admin"] else 0
    role_value = st.selectbox("新角色", ["physician", "admin"], index=role_index, key=f"role_{selected_user['id']}")
    if st.button("更新角色", type="primary", key=f"update_role_{selected_user['id']}"):
        try:
            update_resp = requests.patch(
                f"{BACKEND_URL}/api/admin/users/{selected_user['id']}/role",
                json={"role": role_value},
                headers=headers,
                timeout=20,
            )
            if update_resp.status_code == 200:
                st.success("角色更新成功")
                st.rerun()
            else:
                st.error(f"更新失败: {update_resp.text}")
        except requests.exceptions.RequestException as exc:
            st.error(f"请求失败: {exc}")

    st.markdown("#### 重置密码")
    new_user_password = st.text_input("新密码", type="password", key=f"pwd_{selected_user['id']}")
    if st.button("重置密码", key=f"reset_pwd_{selected_user['id']}"):
        if len(new_user_password) < 6:
            st.error("密码长度必须至少6位")
        else:
            try:
                pwd_resp = requests.post(
                    f"{BACKEND_URL}/api/admin/users/{selected_user['id']}/password",
                    json={"new_password": new_user_password},
                    headers=headers,
                    timeout=20,
                )
                if pwd_resp.status_code == 200:
                    st.success("密码已更新")
                else:
                    st.error(f"重置失败: {pwd_resp.text}")
            except requests.exceptions.RequestException as exc:
                st.error(f"请求失败: {exc}")

with action_col2:
    st.markdown("#### 删除用户")
    st.warning("删除用户会同时清理其患者与检测记录。")
    confirm_name = st.text_input("输入用户名确认删除", key=f"confirm_{selected_user['id']}")
    if st.button("删除用户", type="primary", key=f"delete_{selected_user['id']}"):
        if confirm_name.strip() != selected_user["username"]:
            st.error("输入的用户名不匹配")
        else:
            try:
                del_resp = requests.delete(
                    f"{BACKEND_URL}/api/admin/users/{selected_user['id']}",
                    headers=headers,
                    timeout=20,
                )
                if del_resp.status_code == 200:
                    st.success("用户已删除")
                    st.rerun()
                else:
                    st.error(f"删除失败: {del_resp.text}")
            except requests.exceptions.RequestException as exc:
                st.error(f"请求失败: {exc}")
