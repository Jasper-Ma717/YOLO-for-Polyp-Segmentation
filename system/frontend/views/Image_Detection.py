import streamlit as st
import requests
from PIL import Image
import sys
from pathlib import Path
import math

# Add relative path
FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, fetch_patients, get_auth_headers

ensure_login()

st.title("📷 批量图片检测站")

patients = fetch_patients()
if not patients:
    st.info("请先到患者管理页面创建患者！")
    st.stop()

patient_options = {f"#{p['id']} - {p['name']} ({p['gender']}, {p['age']}岁)": p["id"] for p in patients}
selected_patient_label = st.selectbox("选择患者进行绑定", list(patient_options.keys()))
selected_patient_id = patient_options[selected_patient_label]

st.markdown("---")

uploaded_files = st.file_uploader("支持批量上传 (您可以一次性框选多张图片进入队列)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    # --- 分页逻辑 ---
    items_per_page = 9
    total_pages = math.ceil(len(uploaded_files) / items_per_page)
    
    if "img_det_page" not in st.session_state:
        st.session_state.img_det_page = 1
        
    # 页码越界保护
    if st.session_state.img_det_page > total_pages:
        st.session_state.img_det_page = total_pages
        
    st.markdown("### 待处理队列预览")
    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("⬅️ 上一页", disabled=st.session_state.img_det_page <= 1, key="img_prev"):
            st.session_state.img_det_page -= 1
            st.rerun()
    with col_page:
        st.markdown(f"<div style='text-align: center; margin-top: 8px;'>当前第 {st.session_state.img_det_page} 页 / 共 {total_pages} 页 (总计 {len(uploaded_files)} 张图像)</div>", unsafe_allow_html=True)
    with col_next:
        if st.button("下一页 ➡️", disabled=st.session_state.img_det_page >= total_pages, key="img_next"):
            st.session_state.img_det_page += 1
            st.rerun()

    start_idx = (st.session_state.img_det_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_files = uploaded_files[start_idx:end_idx]
    
    cols = st.columns(3)
    for idx, file in enumerate(current_files):
        with cols[idx % 3]:
            st.image(Image.open(file), caption=file.name, use_container_width=True)

    st.markdown("---")
    
    if st.button("🚀 开始批量推理全部图片", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 使用 session_state 来保存结果，避免翻页时数据丢失
        if "img_results" not in st.session_state:
            st.session_state.img_results = []
        else:
            st.session_state.img_results.clear()
            
        for i, f in enumerate(uploaded_files):
            status_text.text(f"正在处理第 {i+1}/{len(uploaded_files)} 张: {f.name}")
            f.seek(0)
            files = {"file": (f.name, f.getvalue(), f.type)}
            
            try:
                res = requests.post(
                    f"{BACKEND_URL}/api/detection/image",
                    files=files,
                    data={"patient_id": selected_patient_id},
                    headers=get_auth_headers(),
                    timeout=120
                )
                if res.status_code == 200 and res.json()["status"] == "success":
                    data = res.json()["data"]
                    st.session_state.img_results.append({
                        "name": f.name,
                        "cnt": data["polyp_count"],
                        "url": f"{BACKEND_URL}/static/results/{data['result_filename']}"
                    })
            except Exception as e:
                st.error(f"{f.name} 处理失败: {str(e)}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.success("批量推理完成！")
        st.session_state.img_det_page = 1 # 处理完后重置页码以查看结果
        st.rerun()

# --- 结果展示（支持结果同样翻页） ---
if "img_results" in st.session_state and len(st.session_state.img_results) > 0:
    st.markdown("### 📊 批量检测结果")
    
    res_items_per_page = 9
    res_total_pages = math.ceil(len(st.session_state.img_results) / res_items_per_page)
    
    if "img_res_page" not in st.session_state:
        st.session_state.img_res_page = 1
        
    if st.session_state.img_res_page > res_total_pages:
        st.session_state.img_res_page = res_total_pages
        
    rc_prev, rc_page, rc_next = st.columns([1, 2, 1])
    with rc_prev:
        if st.button("⬅️ 结果上一页", disabled=st.session_state.img_res_page <= 1, key="res_prev"):
            st.session_state.img_res_page -= 1
            st.rerun()
    with rc_page:
        st.markdown(f"<div style='text-align: center; margin-top: 8px;'>结果第 {st.session_state.img_res_page} 页 / 共 {res_total_pages} 页</div>", unsafe_allow_html=True)
    with rc_next:
        if st.button("结果下一页 ➡️", disabled=st.session_state.img_res_page >= res_total_pages, key="res_next"):
            st.session_state.img_res_page += 1
            st.rerun()

    r_start_idx = (st.session_state.img_res_page - 1) * res_items_per_page
    r_end_idx = r_start_idx + res_items_per_page
    current_res = st.session_state.img_results[r_start_idx:r_end_idx]
    
    res_cols = st.columns(3)
    for i, res in enumerate(current_res):
        with res_cols[i % 3]:
            st.image(res["url"], caption=f"{res['name']} | 息肉数量: {res['cnt']}", use_container_width=True)
