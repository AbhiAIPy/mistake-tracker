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
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
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
    st.caption("Upload a file or ask anything!")
    
    chat_file = st.file_uploader("Upload file (Image/PDF)", type=["png", "jpg", "pdf", "txt"])
    user_msg = st.chat_input("Ask a question...")
    
    if user_msg:
        with st.chat_message("user"):
            st.write(user_msg)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = chat_with_gemini(user_msg, chat_file)
                st.write(response)

# --- 📊 MAIN APP INTERFACE ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

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
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, top.title(), nts, "No"])
                st.success("Entry Saved!")

with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['dt'] = pd.to_datetime(df['Timestamp'])
        df = df.sort_values('dt', ascending=True)

        for i, row in df.iterrows():
            sheet_idx = data.index(row.tolist()) + 1
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                c1, c2, c3 = st.columns([1, 1, 1])
                
                with c1:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with c2:
                    lab = "✅ Mastered" if row['Mastered'] == "Yes" else "⬜ Mark Done"
                    if st.button(lab, key=f"m{i}"):
                        new = "Yes" if row['Mastered'] == "No" else "No"
                        worksheet.update_cell(sheet_idx, 6, new)
                        st.rerun()
                with c3:
                    # DELETE WITH CONFIRMATION
                    del_p = st.popover("🗑️ Delete")
                    del_p.warning("Delete permanently?")
                    if del_p.button("Yes, Confirm", key=f"d{i}"):
                        worksheet.delete_rows(sheet_idx)
                        st.rerun()
    else:
        st.info("No records yet.")

with tab3:
    st.subheader("Random Revision")
    if st.button("🎯 Get Challenge"):
        all_data = worksheet.get_all_values()
        if len(all_data) > 1:
            df_q = pd.DataFrame(all_data[1:], columns=all_data[0])
            pick = df_q[df_q['Mastered'] != "Yes"].sample(1).iloc[0]
            st.image(pick['ImageURL'])
            st.write(f"**{pick['Subject']}**: {pick['Topic']}")

with tab4:
    if st.button("📄 Generate Revision PDF"):
        st.info("PDF Generation logic connected.")
