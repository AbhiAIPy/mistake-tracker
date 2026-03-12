import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import google.generativeai as genai  # <--- New Official Library
import base64

# --- ⚙️ CONFIGURATION ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    # Configure the official library
    genai.configure(api_key=GEMINI_API_KEY)
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

# --- 🤖 THE "LIBRARY" FIX ---
def chat_with_gemini(prompt, uploaded_file=None):
    try:
        # We initialize the model using the library's method
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        content_parts = [prompt]
        
        if uploaded_file:
            # Format the image for the library
            img_data = {
                "mime_type": uploaded_file.type,
                "data": uploaded_file.getvalue()
            }
            content_parts.append(img_data)
        
        response = model.generate_content(content_parts)
        return response.text
    except Exception as e:
        # This will tell us if it's a Permission error, Quota error, or something else
        return f"Library Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    if st.button("🗑️ Clear History"):
        st.session_state.messages = []
        st.rerun()

    chat_file = st.file_uploader("Upload Image/PDF", type=["png", "jpg", "pdf", "txt"])
    
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
        
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Gemini is thinking..."):
                response = chat_with_gemini(prompt, chat_file)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

with tab1:
    up = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Notes")
        if st.form_submit_button("🚀 Save Mistake") and up:
            r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
            if r.status_code == 200:
                url = r.json()["data"]["image"]["url"]
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, topic.title(), notes, "No"])
                st.success("Saved!")

with tab2:
    raw_data = worksheet.get_all_values()
    if len(raw_data) > 1:
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        # Dashboard Logic
        st.caption("Filters:")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📅 7 Days"): st.session_state.f_date = 7
        with c2:
            if st.button("🗓️ 14 Days"): st.session_state.f_date = 14
        with c3:
            if st.button("⏳ Unmastered"): st.session_state.f_date = 0

        st.divider()
        cs1, cs2 = st.columns([2, 1])
        with cs1: search = st.text_input("🔍 Search Topic/Notes")
        with cs2: f_sub = st.selectbox("Subject Filter", ["All"] + sorted(list(df['Subject'].unique())))

        f_df = df.copy()
        if 'f_date' in st.session_state:
            if st.session_state.f_date > 0:
                f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
            else:
                f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        
        if f_sub != "All": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        f_df = f_df.sort_values('dt', ascending=True)
        for _, row in f_df.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                cols = st.columns([1, 1, 1])
                with cols[0]:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with cols[1]:
                    mastered = row['Mastered'].strip().upper() == "YES"
                    if st.button("✅" if mastered else "⬜", key=f"m_{row['SheetRow']}"):
                        worksheet.update_cell(row['SheetRow'], 6, "Yes" if not mastered else "No")
                        st.rerun()
                with cols[2]:
                    del_p = st.popover("🗑️")
                    if del_p.button("Confirm", key=f"d_{row['SheetRow']}"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("No records.")

with tab3:
    if st.button("🎲 Random Mistake"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            pend = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not pend.empty:
                p = pend.sample(1).iloc[0]
                st.image(p['ImageURL'])
                st.write(f"**{p['Subject']}**: {p['Topic']}")
