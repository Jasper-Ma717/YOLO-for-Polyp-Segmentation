import streamlit as st
import pandas as pd
import requests
import sys
from pathlib import Path
import math

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, get_auth_headers

ensure_login()

st.title("📊 历史记录与结果管理")

st.sidebar.markdown("### 导出中心")

try:
    response = requests.get(f"{BACKEND_URL}/api/history/", headers=get_auth_headers(), timeout=30)
    if response.status_code == 200:
        res_data = response.json()
        if res_data["status"] == "success":
            records = res_data["data"]

            if len(records) > 0:
                df = pd.DataFrame(records)
                
                st.sidebar.download_button(
                    label="⬇️ 导出所有综合检测结果 (CSV)",
                    data=df.to_csv(index=False).encode('utf-8-sig'),
                    file_name='综合检测历史记录.csv',
                    mime='text/csv'
                )

                st.subheader("详细历史记录 (支持翻页、修改与删除)")
                
                items_per_page = 10
                total_pages = math.ceil(len(records) / items_per_page)
                
                if "history_page" not in st.session_state:
                    st.session_state.history_page = 1
                
                col_prev, col_page, col_next = st.columns([1, 2, 1])
                with col_prev:
                    if st.button("⬅️ 上一页", disabled=st.session_state.history_page <= 1):
                        st.session_state.history_page -= 1
                        st.rerun()
                with col_page:
                    st.write(f"当前第 {st.session_state.history_page} 页 / 共 {total_pages} 页")
                with col_next:
                    if st.button("下一页 ➡️", disabled=st.session_state.history_page >= total_pages):
                        st.session_state.history_page += 1
                        st.rerun()

                start_idx = (st.session_state.history_page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                current_records = records[start_idx:end_idx]

                for rec in current_records:
                    with st.expander(f"ID:{rec['id']} - {rec['patient_name']} ({rec['task_type']}) - {rec['created_at'][:10]}"):
                        c1, c2, c3, c4 = st.columns([1.5, 2, 1, 1])
                        with c1:
                            st.write(f"**原文件:** {rec['filename']}")
                            st.write(f"**总耗时:** {rec['processing_time_ms']:.2f} ms")
                        with c2:
                            st.write(f"**当前息肉数量:** {rec['polyp_count']}")
                            file_url = f"{BACKEND_URL}/static/results/{rec['saved_path']}"
                            if rec['task_type'] == 'video':
                                st.video(file_url)
                            else:
                                st.image(file_url, use_container_width=True)
                        with c3:
                            new_count = st.number_input("修改息肉数量", value=rec['polyp_count'], min_value=0, key=f"cnt_{rec['id']}")
                            if st.button("✅ 更新记录", key=f"upd_{rec['id']}"):
                                patch_res = requests.patch(
                                    f"{BACKEND_URL}/api/history/{rec['id']}", 
                                    json={"polyp_count": new_count}, 
                                    headers=get_auth_headers()
                                )
                                if patch_res.status_code == 200:
                                    st.success("已更新")
                                    st.rerun()
                                else:
                                    st.error("更新失败，无权限或服务错误")
                        with c4:
                            st.write("<br>", unsafe_allow_html=True)
                            if rec['task_type'] == 'video':
                                st.markdown(f"[⬇️ 点击下载结果视频]({file_url})")
                            else:
                                st.markdown(f"[⬇️ 点击下载结果图片]({file_url})")
                                
                            st.write("---")
                            if st.button("🗑️ 删除记录", type="primary", key=f"del_{rec['id']}"):
                                del_res = requests.delete(f"{BACKEND_URL}/api/history/{rec['id']}", headers=get_auth_headers())
                                if del_res.status_code == 200:
                                    st.success("记录已删除")
                                    if len(current_records) == 1 and st.session_state.history_page > 1:
                                        st.session_state.history_page -= 1
                                    st.rerun()
                                else:
                                    st.error("删除失败")
                                    
            else:
                st.info("暂无历史记录，请先前往检测页面进行图像或视频检测。")
        else:
            st.error("获取检测历史失败。")
except requests.exceptions.ConnectionError:
    st.error("后端连接失败！请在终端运行：uvicorn system.backend.main:app --reload")