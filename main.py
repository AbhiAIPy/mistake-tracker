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
    st.error("Secrets missing! Check Secrets.")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error("Auth Error: Check gcp_service_account in Secrets."); st.stop()

creds = get_creds()
gc = gspread.authorize(creds)
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 SIDEBAR CHATBOT FUNCTION ---
def chat_with_gemini(prompt, uploaded_file=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    parts = [{"text": prompt}]
    
    if uploaded_file:
        file_bytes = base64.b64encode(uploaded_file.getvalue()).decode()
        parts.append({
            "inline_data": {
                "mime_type": uploaded_file.type,
                "data": file_bytes
            }
        })
    
    payload = {"contents": [{"parts": parts}]}
    try:
        res = requests.post(url, json=payload)
        return res.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "I'm having trouble processing that. Please try again."

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# --- 📟 SIDEBAR CHATBOT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    st.caption("Ask anything or upload files!")
    
    chat_file = st.file_uploader("Upload file (Image/PDF)", type=["png", "jpg", "pdf", "txt"])
    
    # Initialize chat history if it doesn't exist
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is 15% of 80?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = chat_with_gemini(prompt, chat_file)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP INTERFACE ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD ---
with tab1:
    up = st.file_uploader("Upload Mistake Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        top = st.text_input("Topic")
        nts = st.text_area("Notes")
        if st.form_submit_button("🚀 Save Mistake") and up:
            r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
            if r.status_code == 200:
                url = r.json()["data"]["image"]["url"]
                # Store data
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, top.title(), nts, "No"])
                st.success("Entry Saved!")

# --- TAB 2: REVIEW ---
with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        # Create DataFrame but keep original indices for gspread
        df = pd.DataFrame(data[1:], columns=data[0])
        df['OriginalRowIndex'] = range(2, len(df) + 2) # Sheets start at 1, header is 1
        
        # Safe Date Conversion
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        df = df.sort_values('dt', ascending=True)

        for i, row in df.iterrows():
            sheet_row = int(row['OriginalRowIndex'])
            
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                c1, c2, c3 = st.columns([1, 1, 1])
                
                with c1:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with c2:
                    is_mastered = row['Mastered'].strip().lower() == "yes"
                    lab = "✅ Mastered" if is_mastered else "⬜ Mark Done"
                    if st.button(lab, key=f"m{sheet_row}"):
                        new_val = "No" if is_mastered else "Yes"
                        worksheet.update_cell(sheet_row, 6, new_val)
                        st.rerun()
                with c3:
                    # DELETE WITH CONFIRMATION
                    del_p = st.popover("🗑️ Delete")
                    del_p.warning("Permanently delete this?")
                    if del_p.button("Yes, Confirm", key=f"d{sheet_row}", type="primary"):
                        worksheet.delete_rows(sheet_row)
                        st.rerun()
    else:
        st.info("No records yet.")

# --- TAB 3: QUIZ ---
with tab3:
    if st.button("🎯 Get Challenge"):
        all_data = worksheet.get_all_values()
        if len(all_data) > 1:
            df_q = pd.DataFrame(all_data[1:], columns=all_data[0])
            unsolved = df_q[df_q['Mastered'].str.lower() != "yes"]
            if not unsolved.empty:
                pick = unsolved.sample(1).iloc[0]
                st.image(pick['ImageURL'])
                st.write(f"**{pick['Subject']}**: {pick['Topic']}")
            else:
                st.success("All mistakes mastered!")

# --- TAB 4: PRINT ---
with tab4:
    st.info("The Revision PDF will include all non-mastered mistakes.")
    # (Your PDF logic goes here)
