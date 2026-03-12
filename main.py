import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
import json

# --- ⚙️ CONFIGURATION ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    # For UK/EU, we specify the London region
    REGION = "europe-west2" 
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

# --- 🤖 UK/EU COMPLIANT AI LOGIC (Vertex AI Style) ---
def chat_with_gemini(prompt, uploaded_file=None):
    # This URL uses the stable production endpoint that works in the UK
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    parts = [{"text": prompt}]
    
    if uploaded_file:
        img_b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
        parts.append({
            "inline_data": {
                "mime_type": uploaded_file.type,
                "data": img_b64
            }
        })
    
    payload = {"contents": [{"parts": parts}]}

    try:
        # We try V1 first, but if it fails, we provide a very specific UK error message
        response = requests.post(url, json=payload)
        res_json = response.json()
        
        if response.status_code == 200:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            msg = res_json.get('error', {}).get('message', '')
            if "location" in msg.lower() or "not available" in msg.lower():
                return "🚨 **UK/EU Region Restriction:** Your Google AI Key is blocked by UK privacy laws for this specific tool. Please go to Google AI Studio, create a *new* key, and ensure 'Pay-as-you-go' (still has a free tier) is enabled, or use a VPN set to the USA."
            return f"Error: {msg}"
            
    except Exception as e:
        return f"System Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    st.caption("UK/EU Stable Mode")
    
    if st.button("🗑️ Clear History"):
        st.session_state.messages = []
        st.rerun()

    chat_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    if "messages" not in st.session_state: st.session_state.messages = []
        
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
        
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Processing in UK Region..."):
                response = chat_with_gemini(prompt, chat_file)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP TABS (DASHBOARD & SEARCH RESTORED) ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

with tab1:
    up = st.file_uploader("Upload Mistake", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Notes")
        if st.form_submit_button("🚀 Save") and up:
            r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
            if r.status_code == 200:
                url = r.json()["data"]["image"]["url"]
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, topic.title(), notes, "No"])
                st.success("Logged!")

with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        st.caption("Dashboard Filters:")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📅 7 Days"): st.session_state.f_date = 7
        with c2:
            if st.button("🗓️ 14 Days"): st.session_state.f_date = 14
        with c3:
            if st.button("⏳ Unmastered"): st.session_state.f_date = 0

        st.divider()
        cs1, cs2 = st.columns([2, 1])
        with cs1: search = st.text_input("🔍 Search Topic")
        with cs2: f_sub = st.selectbox("Subject", ["All"] + sorted(list(df['Subject'].unique())))

        f_df = df.copy()
        if 'f_date' in st.session_state:
            if st.session_state.f_date > 0:
                f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
            else:
                f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        
        if f_sub != "All": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        for _, row in f_df.sort_values('dt', ascending=True).iterrows():
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                cols = st.columns([1, 1, 1])
                with cols[0]:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with cols[1]:
                    m = row['Mastered'].strip().upper() == "YES"
                    if st.button("✅" if m else "⬜", key=f"m_{row['SheetRow']}"):
                        worksheet.update_cell(row['SheetRow'], 6, "Yes" if not m else "No")
                        st.rerun()
                with cols[2]:
                    if st.button("🗑️", key=f"d_{row['SheetRow']}"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("No data.")

with tab3:
    if st.button("🎲 Quiz"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            p = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not p.empty:
                sel = p.sample(1).iloc[0]
                st.image(sel['ImageURL'])
                st.write(f"**{sel['Subject']}**: {sel['Topic']}")

with tab4:
    st.info("Revision Export logic.")
