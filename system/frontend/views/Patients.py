import streamlit as st
import requests
import pandas as pd
import sys
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.append(str(FRONTEND_DIR))

from system.frontend.common import BACKEND_URL, ensure_login, get_auth_headers, fetch_patients  

# set_page_config must be in app.py typically
ensure_login()

st.title("👥 患者档案与检测报告")
st.caption("创建、编辑、删除患者档案，查看指定患者并导出报表数据。")

headers = get_auth_headers()

with st.expander("➕ 新增患者", expanded=False):
    with st.form("create_patient"):
        name = st.text_input("患者姓名")
        age = st.number_input("年龄", min_value=0, max_value=130, value=50)       
        gender = st.selectbox("性别", ["男", "女", "其他"])
        medical_history = st.text_area("病史信息", value="")
        submit = st.form_submit_button("创建患者档案", type="primary")

    if submit:
        payload = {
            "name": name.strip(),
            "age": int(age),
            "gender": gender,
            "medical_history": medical_history.strip(),
        }
        if not payload["name"]:
            st.error("患者姓名不能为空")
        else:
            try:
                resp = requests.post(f"{BACKEND_URL}/api/patients/", json=payload, headers=headers, timeout=20)   
                if resp.status_code == 200:
                    st.success("患者创建成功")
                    st.rerun()
                else:
                    st.error(f"创建失败: {resp.text}")
            except requests.exceptions.RequestException as exc:
                st.error(f"请求失败: {exc}")

st.markdown("---")
st.subheader("我的患者管理")

# 综合视图：患者列表 + 编辑/删除 + 查看该患者所有历史记录逻辑
patients = fetch_patients()
if not patients:
    st.info("暂无患者，请先创建。")
else:
    df_patients = pd.DataFrame(patients)
    # 显示概览
    st.dataframe(df_patients[["id", "name", "gender", "age", "created_at"]].rename(columns={
        "id": "ID", "name": "姓名", "gender": "性别", "age": "年龄", "created_at": "建档时间"
    }), use_container_width=True)

    # ========== 编辑 / 删除患者 ==========
    st.markdown("### ✏️ 编辑或删除患者")
    patient_map_edit = {f"#{p['id']} - {p['name']}": p for p in patients}
    sel_edit_label = st.selectbox("选择患者", list(patient_map_edit.keys()), key="sel_edit")
    sel_patient = patient_map_edit[sel_edit_label]

    tab_edit, tab_delete = st.tabs(["📝 编辑信息", "🗑️ 删除患者"])

    with tab_edit:
        with st.form("edit_patient_form"):
            edit_name = st.text_input("姓名", value=sel_patient["name"])
            edit_age = st.number_input("年龄", min_value=0, max_value=130, value=sel_patient["age"])
            edit_gender = st.selectbox(
                "性别", ["男", "女", "其他"],
                index=["男", "女", "其他"].index(sel_patient["gender"]) if sel_patient["gender"] in ["男", "女", "其他"] else 0,
            )
            edit_mh = st.text_area("病史信息", value=sel_patient.get("medical_history", ""))
            edit_btn = st.form_submit_button("保存修改", type="primary")

        if edit_btn:
            update_payload = {
                "name": edit_name.strip(),
                "age": int(edit_age),
                "gender": edit_gender,
                "medical_history": edit_mh.strip(),
            }
            try:
                resp = requests.put(
                    f"{BACKEND_URL}/api/patients/{sel_patient['id']}",
                    json=update_payload, headers=headers, timeout=20,
                )
                if resp.status_code == 200:
                    st.success("患者信息已更新")
                    st.rerun()
                else:
                    st.error(f"更新失败: {resp.text}")
            except requests.exceptions.RequestException as exc:
                st.error(f"请求失败: {exc}")

    with tab_delete:
        st.warning(f"⚠️ 删除患者 **{sel_patient['name']}** 将同时删除该患者所有关联的检测记录，此操作不可撤销！")
        confirm_name = st.text_input("请输入患者姓名以确认删除", key="confirm_del_name")
        if st.button("确认删除", type="primary", key="btn_del_patient"):
            if confirm_name.strip() != sel_patient["name"]:
                st.error("输入的姓名不匹配，删除已取消。")
            else:
                try:
                    resp = requests.delete(
                        f"{BACKEND_URL}/api/patients/{sel_patient['id']}",
                        headers=headers, timeout=20,
                    )
                    if resp.status_code == 200:
                        st.success("患者已删除")
                        st.rerun()
                    else:
                        st.error(f"删除失败: {resp.text}")
                except requests.exceptions.RequestException as exc:
                    st.error(f"请求失败: {exc}")

    st.markdown("---")
    
    st.markdown("### 🔍 患者检测报告导出")
    st.info("选择一位患者以查看他所有的历史检测情况并导出综合结果报表。")
    
    patient_map = {f"#{p['id']} - {p['name']}": p['id'] for p in patients}
    sel_p_label = st.selectbox("选择目标患者", list(patient_map.keys()), key="sel_export")
    sel_p_id = patient_map[sel_p_label]
    
    # 拉取该医生全部历史中对应患的信息
    try:
        hist_resp = requests.get(f"{BACKEND_URL}/api/history/", headers=headers, timeout=20)
        if hist_resp.status_code == 200:
            all_hist = hist_resp.json()["data"]
            # 过滤出当前患者
            p_hist = [h for h in all_hist if h.get("patient_id") == sel_p_id]
            
            if p_hist:
                df_hist = pd.DataFrame(p_hist)
                st.write(f"共发现 {len(df_hist)} 条相关检测记录。")
                st.dataframe(df_hist[["id", "task_type", "filename", "polyp_count", "created_at"]], use_container_width=True)
                
                csv_data = df_hist.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label=f"⬇️ 导出【{sel_p_label.split(' - ')[1]}】的综合检测结果 (CSV)",
                    data=csv_data,
                    file_name=f'患者_{sel_p_label.split(" - ")[1]}_检测报表.csv',
                    mime='text/csv',
                    type="primary"
                )
                pdf_state_key = f"patient_report_{sel_p_id}"
                if st.button(f"生成【{sel_p_label.split(' - ')[1]}】PDF 报告", key=f"gen_pdf_{sel_p_id}"):
                    try:
                        pdf_resp = requests.get(
                            f"{BACKEND_URL}/api/history/patient/{sel_p_id}/report-pdf",
                            headers=headers,
                            timeout=30,
                        )
                        if pdf_resp.status_code == 200:
                            st.session_state[pdf_state_key] = pdf_resp.content
                        else:
                            st.error("PDF 报告生成失败")
                    except requests.exceptions.RequestException:
                        st.warning("PDF 报告生成失败，请稍后重试。")

                if st.session_state.get(pdf_state_key):
                    st.download_button(
                        label=f"⬇️ 下载【{sel_p_label.split(' - ')[1]}】PDF 报告",
                        data=st.session_state[pdf_state_key],
                        file_name=f'患者_{sel_p_label.split(" - ")[1]}_检测报告.pdf',
                        mime='application/pdf',
                        type="secondary"
                    )
            else:
                st.warning("该患者尚未进行任何图像或视频检测。")
    except Exception as e:
        st.error("拉取数据失败")
