import streamlit as st
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import ensure_login

ensure_login()

st.title("🏠 欢迎使用息肉智能诊断系统")
st.caption("本系统集成 YOLO 分割推理、患者档案管理、结果追踪、统计分析与审计能力。")

hero_left, hero_right = st.columns([1.4, 1])
with hero_left:
    st.markdown(
        """
        ### 系统能力
        - 支持内镜图片与视频的息肉检测和分割
        - 通过患者档案与检测历史建立完整业务链路
        - 提供统计仪表盘、PDF 报告与管理员审计能力
        - 采用 Streamlit + FastAPI + SQLite 的前后端分离架构
        """
    )
with hero_right:
    with st.container(border=True):
        st.metric("当前可用模块", 8)
        st.metric("管理能力", "用户 / 审计 / 统计")
        st.metric("AI 推理对象", "图片 + 视频")

st.markdown("---")
st.subheader("快捷入口")

cards = [
    ("📈 数据统计", "查看检测趋势、医生工作量和患者分布", "views/Dashboard.py", "前往数据统计"),
    ("👥 患者管理", "维护患者档案并导出患者级检测报告", "views/Patients.py", "前往患者管理"),
    ("📷 图片检测", "上传单张或批量图片进行模型推理", "views/Image_Detection.py", "前往图片检测"),
    ("🎬 视频检测", "上传视频并执行逐帧检测", "views/Video_Detection.py", "前往视频检测"),
    ("📊 历史记录", "浏览历史结果并查看详情", "views/History.py", "前往历史记录"),
    ("👤 个人中心", "修改密码并管理当前账户", "views/Profile.py", "前往个人中心"),
]

for row_start in range(0, len(cards), 3):
    cols = st.columns(3)
    for col, card in zip(cols, cards[row_start:row_start + 3]):
        title, desc, page_path, button_text = card
        with col:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(desc)
                if st.button(button_text, key=f"nav_{page_path}", use_container_width=True):
                    st.switch_page(page_path)
