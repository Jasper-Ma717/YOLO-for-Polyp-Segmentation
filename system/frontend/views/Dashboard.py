import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, get_auth_headers

ensure_login()

st.title("📈 数据统计仪表盘")

headers = get_auth_headers()

try:
    resp = requests.get(f"{BACKEND_URL}/api/statistics/overview", headers=headers, timeout=30)
except requests.exceptions.ConnectionError:
    st.error("后端连接失败！请确保后端服务正在运行。")
    st.stop()

if resp.status_code != 200:
    st.error("获取统计数据失败。")
    st.stop()

data = resp.json()["data"]

# ===================== 核心指标卡片 =====================
st.subheader("核心指标")
c1, c2, c3, c4 = st.columns(4)
c1.metric("检测总次数", data["total_detections"])
c2.metric("患者总数", data["total_patients"])
c3.metric("平均处理耗时", f"{data['avg_processing_ms']:.1f} ms")
c4.metric("平均推理耗时", f"{data['avg_inference_ms']:.1f} ms")

st.markdown("---")

# ===================== 图表行 1：息肉分布 + 任务类型 =====================
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 息肉检出分布")
    polyp_df = pd.DataFrame([
        {"类别": "检出息肉", "数量": data["polyp_positive"]},
        {"类别": "未检出息肉", "数量": data["polyp_negative"]},
    ])
    if polyp_df["数量"].sum() > 0:
        fig_pie = px.pie(
            polyp_df, names="类别", values="数量",
            color="类别",
            color_discrete_map={"检出息肉": "#EF553B", "未检出息肉": "#636EFA"},
            hole=0.4,
        )
        fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=320)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("暂无检测数据")

with col_right:
    st.markdown("#### 检测任务类型分布")
    type_df = pd.DataFrame(data["type_distribution"])
    if type_df["count"].sum() > 0:
        fig_bar_type = px.bar(
            type_df, x="type", y="count",
            color="type",
            labels={"type": "任务类型", "count": "次数"},
            text_auto=True,
        )
        fig_bar_type.update_layout(
            margin=dict(t=20, b=20, l=20, r=20), height=320,
            showlegend=False,
        )
        st.plotly_chart(fig_bar_type, use_container_width=True)
    else:
        st.info("暂无检测数据")

st.markdown("---")

# ===================== 图表行 2：每日趋势 =====================
st.markdown("#### 近期检测趋势（最近 30 天）")
if data["daily_trend"]:
    daily_df = pd.DataFrame(data["daily_trend"])
    daily_df = daily_df.sort_values("date")
    fig_line = px.area(
        daily_df, x="date", y="count",
        labels={"date": "日期", "count": "检测次数"},
    )
    fig_line.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300)
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("暂无检测记录")

st.markdown("---")

# ===================== 图表行 3：排行榜 =====================
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("#### 患者检测频次 Top 5")
    if data["top_patients"]:
        tp_df = pd.DataFrame(data["top_patients"])
        fig_top = px.bar(
            tp_df, x="count", y="name", orientation="h",
            labels={"name": "患者", "count": "检测次数"},
            text_auto=True,
            color_discrete_sequence=["#00CC96"],
        )
        fig_top.update_layout(
            margin=dict(t=20, b=20, l=20, r=20), height=300,
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("暂无患者检测数据")

with col_b:
    st.markdown("#### 医生工作量排行")
    if data["doctor_workload"]:
        dw_df = pd.DataFrame(data["doctor_workload"])
        fig_doc = px.bar(
            dw_df, x="count", y="username", orientation="h",
            labels={"username": "医生", "count": "检测次数"},
            text_auto=True,
            color_discrete_sequence=["#AB63FA"],
        )
        fig_doc.update_layout(
            margin=dict(t=20, b=20, l=20, r=20), height=300,
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_doc, use_container_width=True)
    else:
        st.info("仅管理员可查看全局医生工作量，或暂无数据。")
