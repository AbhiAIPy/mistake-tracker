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

# --- 🤖 SELF-HEALING AI LOGIC ---
def get_working_model():
    """Asks the API which models are available to avoid 404 errors."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
    try:
        res = requests.get(url).json()
        models = [m['name'] for m in res.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        # Prioritize flash, then pro, then whatever is first
        for m in models:
            if 'flash' in m: return m
        for m in models:
            if 'pro' in m: return m
        return models[0] if models else None
    except:
        return None

def chat_with_gemini(prompt, uploaded_file=None):
    model_path = get_working_model()
    if not model_path:
        return "System Error: Could not find any active models for this API key."

    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={GEMINI_API_KEY}"
    
    parts = [{"text": prompt}]
    if uploaded_file:
        img_b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
        parts.append({"inline_data": {"mime_type": uploaded_file.type, "data": img_b64}})
    
    payload = {"contents": [{"parts": parts}]}

    try:
        response = requests.post(url, json=payload)
        res_json = response.json()
        if response.status_code == 200:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"API Error ({response.status_code}): {res_json.get('error', {}).get('message', 'Unknown')}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# --- 📟 SIDEBAR CHAT ---
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
            with st.spinner("Searching for active model..."):
                response = chat_with_gemini(prompt, chat_file)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP TABS ---
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
                st.success("Mistake Logged!")

with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        st.caption("Quick Filters:")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📅 7 Days"): st.session_state.f_date = 7
        with c2:
            if st.button("🗓️ 14 Days"): st.session_state.f_date = 14
        with c3:
            if st.button("⏳ Unmastered"): st.session_state.f_date = 0

        st.divider()
        cs1, cs2 = st.columns([2, 1])
        with cs1: search = st.text_input("🔍 Search")
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
                    mastered = row['Mastered'].strip().upper() == "YES"
                    if st.button("✅" if mastered else "⬜ Mark Done", key=f"m_{row['SheetRow']}"):
                        worksheet.update_cell(row['SheetRow'], 6, "Yes" if not mastered else "No")
                        st.rerun()
                with cols[2]:
                    del_p = st.popover("🗑️ Delete")
                    if del_p.button("Confirm", key=f"d_{row['SheetRow']}", type="primary"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()

with tab3:
    if st.button("🎲 Get Random Challenge"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            pend = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not pend.empty:
                p = pend.sample(1).iloc[0]
                st.image(p['ImageURL'])
                st.subheader(f"{p['Subject']}: {p['Topic']}")

with tab4:
    st.info("Tab 4: Revision Print mode.")
