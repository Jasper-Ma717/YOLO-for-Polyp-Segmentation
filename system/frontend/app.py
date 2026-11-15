import streamlit as st
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from system.frontend.common
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from system.frontend.common import BACKEND_URL, init_session_state, handle_logout, require_login

st.set_page_config(
    page_title="息肉分割系统",
    page_icon="🩺",
    layout="wide",
)

st.markdown("""
<style>
/* 侧边栏菜单项间距和大小修改 */
[data-testid="stSidebarNav"] ul {
    gap: 12px;
}
[data-testid="stSidebarNav"] a {
    font-size: 18px !important;
    padding: 0.8rem 1rem !important;
    border-radius: 8px;
}
/* 限制主界面图像大小，防止铺开 */
.element-container img {
    max-height: 50vh !important;
    width: auto !important;
    margin: 0 auto;
    border-radius: 6px;
}
.element-container video {
    max-height: 50vh !important;
    width: auto !important;
    margin: 0 auto;
}
</style>
""", unsafe_allow_html=True)

init_session_state()

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"
if "just_registered" not in st.session_state:
    st.session_state.just_registered = False

pages = {
    "系统应用": [
         st.Page("views/Home.py", title="🏠 欢迎页", url_path="home"),
         st.Page("views/Dashboard.py", title="📈 数据统计", url_path="dashboard"),
         st.Page("views/Patients.py", title="👥 患者管理", url_path="patients"),
         st.Page("views/Image_Detection.py", title="📷 图片检测", url_path="image-detection"),
         st.Page("views/Video_Detection.py", title="🎬 视频检测", url_path="video-detection"),
         st.Page("views/History.py", title="📊 历史记录", url_path="history"),
         st.Page("views/Profile.py", title="👤 个人中心", url_path="profile"),
    ]
}

if st.session_state.current_user and st.session_state.current_user.get("role") == "admin":
    pages["系统管理"] = [
        st.Page("views/User_Management.py", title="🛡️ 用户管理", url_path="users"),
        st.Page("views/Audit_Logs.py", title="🧾 审计日志", url_path="audit-logs"),
    ]

pg = st.navigation(pages) if st.session_state.access_token else None

if not st.session_state.access_token:
    # 剧中排版
    st.write("")
    st.write("")
    col1, col2, col3 = st.columns([1, 1.2, 1])
    
    with col2:
        st.markdown("<h2 style='text-align: center;'>🩺 息肉智能诊断系统</h2><br>", unsafe_allow_html=True)
        
        if st.session_state.auth_mode == "login":
            if st.session_state.just_registered:
                st.success("🎉 注册成功！请登录。")
                st.session_state.just_registered = False

            with st.container(border=True):
                st.markdown("<h4 style='text-align: center; color: #4F8BF9;'>用户登录</h4>", unsafe_allow_html=True)
                with st.form("login_form"):
                    username = st.text_input("用户名", placeholder="请输入您的账号")
                    password = st.text_input("密码", type="password", placeholder="请输入密码")
                    st.write("")
                    submit_btn = st.form_submit_button("登 录 🚀", use_container_width=True)
                    
                    if submit_btn:
                        import requests
                        try:
                            res = requests.post(
                                f"{BACKEND_URL}/api/auth/login",
                                data={"username": username, "password": password},
                                timeout=15,
                            )
                            if res.status_code == 200:
                                st.session_state.access_token = res.json()["access_token"]
                                Headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                                user_res = requests.get(f"{BACKEND_URL}/api/auth/me", headers=Headers, timeout=15)
                                if user_res.status_code == 200:
                                    st.session_state.current_user = user_res.json()["data"]  # 修复了 None 的问题，接口返回嵌套 data
                                    st.rerun()
                            else:
                                st.error("用户名或密码错误")
                        except requests.exceptions.ReadTimeout:
                            st.error("登录请求超时，请检查后端是否正常运行。")
                        except requests.exceptions.ConnectionError:
                            st.error("无法连接到后端服务器。")
                        except requests.exceptions.RequestException as exc:
                            st.error(f"登录请求失败：{exc}")
            
            st.write("")
            c1, c2 = st.columns([2, 1])
            c1.markdown("<div style='margin-top: 8px; color: #666;'>没有账号？</div>", unsafe_allow_html=True)
            if c2.button("注册账号 📝", use_container_width=True):
                st.session_state.auth_mode = "register"
                st.rerun()

        elif st.session_state.auth_mode == "register":
            with st.container(border=True):
                st.markdown("<h4 style='text-align: center; color: #4F8BF9;'>新用户注册</h4>", unsafe_allow_html=True)
                with st.form("register_form"):
                    new_username = st.text_input("想要注册的用户名", placeholder="至少3个字符")
                    new_password = st.text_input("设置密码", type="password", placeholder="至少6位")
                    st.write("")
                    reg_btn = st.form_submit_button("确 认 注 册", use_container_width=True)
                    
                    if reg_btn:
                        import requests
                        try:
                            if len(new_password) < 6:
                                st.error("密码长度必须≥6位")
                            elif len(new_username) < 3:
                                st.error("用户名太短")
                            else:
                                # /register 只接收 username 和 password（默认 role 为 physician）
                                user_data = {"username": new_username, "password": new_password}
                                res = requests.post(f"{BACKEND_URL}/api/auth/register", json=user_data, timeout=15)
                                if res.status_code == 200:
                                    st.session_state.auth_mode = "login"
                                    st.session_state.just_registered = True
                                    st.rerun()
                                else:
                                    st.error(f"注册失败：{res.json().get('detail', res.text)}")
                        except requests.exceptions.ReadTimeout:
                            st.error("注册请求超时，请检查后端是否正常运行。")
                        except requests.exceptions.RequestException as exc:
                            st.error(f"请求失败：{exc}")
            
            st.write("")
            if st.button("返回登录", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()

else:
    with st.sidebar:
        st.divider()
        # 修复左下角名称获取
        username = st.session_state.current_user.get('username', '未知用户') if st.session_state.current_user else '未知'
        role = '超级管理' if (st.session_state.current_user and st.session_state.current_user.get('role') == 'admin') else '医生'
        st.markdown(f"**当前登录:** {username} ({role})")
        if st.button("注销退出", type="primary", use_container_width=True):
            handle_logout()
    
    pg.run()
