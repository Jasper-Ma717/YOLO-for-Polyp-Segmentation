import streamlit as st
import requests
import sys
from pathlib import Path
import math

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, fetch_patients, get_auth_headers

ensure_login()

st.title("🎬 批量视频检测站")

patients = fetch_patients()
if not patients:
    st.info("请先到患者管理页面创建患者！")
    st.stop()

patient_options = {f"#{p['id']} - {p['name']} ({p['gender']}, {p['age']}岁)": p["id"] for p in patients}
selected_patient_label = st.selectbox("选择患者进行绑定", list(patient_options.keys()))
selected_patient_id = patient_options[selected_patient_label]

st.markdown("---")

uploaded_videos = st.file_uploader("支持批量上传 (您可以一次性选取多个视频进入队列)", type=['mp4', 'avi'], accept_multiple_files=True)

if uploaded_videos:
    # --- 分页逻辑 ---
    items_per_page = 9
    total_pages = math.ceil(len(uploaded_videos) / items_per_page)
    
    if "vid_det_page" not in st.session_state:
        st.session_state.vid_det_page = 1
        
    if st.session_state.vid_det_page > total_pages:
        st.session_state.vid_det_page = total_pages
        
    st.markdown("### 待处理队列预览")
    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("⬅️ 上一页", disabled=st.session_state.vid_det_page <= 1, key="vid_prev"):
            st.session_state.vid_det_page -= 1
            st.rerun()
    with col_page:
        st.markdown(f"<div style='text-align: center; margin-top: 8px;'>当前第 {st.session_state.vid_det_page} 页 / 共 {total_pages} 页 (总计 {len(uploaded_videos)} 个视频)</div>", unsafe_allow_html=True)
    with col_next:
        if st.button("下一页 ➡️", disabled=st.session_state.vid_det_page >= total_pages, key="vid_next"):
            st.session_state.vid_det_page += 1
            st.rerun()

    start_idx = (st.session_state.vid_det_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_videos = uploaded_videos[start_idx:end_idx]
    
    # 视频同样九宫格布局
    cols = st.columns(3)
    for idx, video in enumerate(current_videos):
        with cols[idx % 3]:
            st.video(video)
            st.caption(video.name)

    st.markdown("---")
    
    if st.button("🚀 开始批量推理全部视频 (将按顺序处理，请耐心等待)", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        if "vid_results" not in st.session_state:
            st.session_state.vid_results = []
        else:
            st.session_state.vid_results.clear()
            
        for i, f in enumerate(uploaded_videos):
            status_text.text(f"正在处理第 {i+1}/{len(uploaded_videos)} 个: {f.name} ...")
            f.seek(0)
            files = {"file": (f.name, f.getvalue(), f.type)}
            
            try:
                res = requests.post(
                    f"{BACKEND_URL}/api/detection/video",
                    files=files,
                    data={"patient_id": selected_patient_id},
                    headers=get_auth_headers(),
                    timeout=3600
                )
                if res.status_code == 200 and res.json()["status"] == "success":
                    data = res.json()["data"]
                    st.session_state.vid_results.append({
                        "name": f.name,
                        "cnt": data["polyp_count"],
                        "url": f"{BACKEND_URL}/static/results/{data['result_filename']}"
                    })
            except Exception as e:
                st.error(f"{f.name} 处理失败: {str(e)}")
            
            progress_bar.progress((i + 1) / len(uploaded_videos))
            
        status_text.success("批量视频推理全部完成！")
        st.session_state.vid_det_page = 1
        # 如果当前还未初始化结果翻页页码，也在此初始化
        st.session_state.vid_res_page = 1
        st.rerun()

# --- 视频结果推断展示（支持翻页） ---
if "vid_results" in st.session_state and len(st.session_state.vid_results) > 0:
    st.markdown("### 📊 批量视频检测结果")
    
    res_items_per_page = 9
    res_total_pages = math.ceil(len(st.session_state.vid_results) / res_items_per_page)
    
    if "vid_res_page" not in st.session_state:
        st.session_state.vid_res_page = 1
        
    if st.session_state.vid_res_page > res_total_pages:
        st.session_state.vid_res_page = res_total_pages
        
    rc_prev, rc_page, rc_next = st.columns([1, 2, 1])
    with rc_prev:
        if st.button("⬅️ 结果上一页", disabled=st.session_state.vid_res_page <= 1, key="vid_res_prev"):
            st.session_state.vid_res_page -= 1
            st.rerun()
    with rc_page:
        st.markdown(f"<div style='text-align: center; margin-top: 8px;'>结果第 {st.session_state.vid_res_page} 页 / 共 {res_total_pages} 页</div>", unsafe_allow_html=True)
    with rc_next:
        if st.button("结果下一页 ➡️", disabled=st.session_state.vid_res_page >= res_total_pages, key="vid_res_next"):
            st.session_state.vid_res_page += 1
            st.rerun()

    r_start_idx = (st.session_state.vid_res_page - 1) * res_items_per_page
    r_end_idx = r_start_idx + res_items_per_page
    current_res = st.session_state.vid_results[r_start_idx:r_end_idx]
    
    res_cols = st.columns(3)
    for i, res in enumerate(current_res):
        with res_cols[i % 3]:
            st.video(res["url"])
            st.caption(f"{res['name']} | 息肉总帧数: {res['cnt']}")
            try:
                video_bytes = requests.get(res["url"]).content
                st.download_button(
                    label=f"⬇️ 下载检测视频",
                    data=video_bytes,
                    file_name=f"detected_{res['name']}",
                    mime="video/mp4",
                    key=f"dl_{i}_{res['name']}"
                )
            except:
                pass
