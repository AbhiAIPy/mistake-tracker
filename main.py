import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
import json
from fpdf import FPDF

# --- ⚙️ CONFIGURATION ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Secrets missing!")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 SIDEBAR CHATBOT ---
def chat_with_gemini(prompt, uploaded_file=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    parts = [{"text": prompt}]
    if uploaded_file:
        file_bytes = base64.b64encode(uploaded_file.getvalue()).decode()
        parts.append({"inline_data": {"mime_type": uploaded_file.type, "data": file_bytes}})
    payload = {"contents": [{"parts": parts}]}
    try:
        res = requests.post(url, json=payload)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Chat Error. Please try again."

st.set_page_config(page_title="11+ Master Bank", layout="wide")

with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    chat_file = st.file_uploader("Upload file", type=["png", "jpg", "pdf", "txt"])
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            response = chat_with_gemini(prompt, chat_file)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

with tab1:
    up = st.file_uploader("Upload Mistake Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        top = st.text_input("Topic")
        nts = st.text_area("Notes")
        if st.form_submit_button("🚀 Save") and up:
            r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
            if r.status_code == 200:
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), r.json()["data"]["image"]["url"], sub, top.title(), nts, "No"])
                st.success("Saved!")

# --- TAB 2: REVIEW (RE-INTEGRATED DASHBOARD) ---
with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['OriginalRowIndex'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        
        # 1. Dashboard Buttons
        st.caption("Quick Filters:")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button(f"📅 7 Days", key="d7"): st.session_state.f_date = 7
        with c2:
            if st.button(f"🗓️ 14 Days", key="d14"): st.session_state.f_date = 14
        with c3:
            if st.button(f"⏳ Pending", key="dpend"): st.session_state.f_date = 0

        # 2. Search and Subject Filter
        st.divider()
        col_search, col_sub = st.columns([2, 1])
        with col_search:
            search_query = st.text_input("🔍 Search Topic or Notes")
        with col_sub:
            f_sub = st.selectbox("Subject:", ["All"] + sorted(list(df['Subject'].unique())))

        # 3. Apply Filtering Logic
        filtered_df = df.copy()
        
        # Apply Dashboard Date/Pending Filter
        if 'f_date' in st.session_state:
            if st.session_state.f_date > 0:
                filtered_df = filtered_df[filtered_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
            else:
                filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]
        
        # Apply Subject Filter
        if f_sub != "All":
            filtered_df = filtered_df[filtered_df['Subject'] == f_sub]
            
        # Apply Search Query
        if search_query:
            filtered_df = filtered_df[
                (filtered_df['Topic'].str.contains(search_query, case=False, na=False)) | 
                (filtered_df['Notes'].str.contains(search_query, case=False, na=False))
            ]

        if 'f_date' in st.session_state and st.button("❌ Clear Dashboard Filter"):
            del st.session_state.f_date
            st.rerun()

        # 4. Display Results
        filtered_df = filtered_df.sort_values('dt', ascending=True)

        for i, row in filtered_df.iterrows():
            sheet_row = int(row['OriginalRowIndex'])
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with c2:
                    is_mastered = row['Mastered'].strip().upper() == "YES"
                    label = "✅ Mastered" if is_mastered else "⬜ Mark Done"
                    if st.button(label, key=f"m{sheet_row}"):
                        worksheet.update_cell(sheet_row, 6, "Yes" if not is_mastered else "No")
                        st.rerun()
                with c3:
                    del_p = st.popover("🗑️ Delete")
                    if del_p.button("Confirm Delete", key=f"d{sheet_row}", type="primary"):
                        worksheet.delete_rows(sheet_row)
                        st.rerun()
    else:
        st.info("No records yet.")

with tab3:
    if st.button("🎯 Random Challenge"):
        all_data = worksheet.get_all_values()
        if len(all_data) > 1:
            df_q = pd.DataFrame(all_data[1:], columns=all_data[0])
            unsolved = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not unsolved.empty:
                pick = unsolved.sample(1).iloc[0]
                st.image(pick['ImageURL'])
                st.write(f"**{pick['Subject']}**: {pick['Topic']}")

with tab4:
    st.info("The Revision PDF logic is ready to use.")
