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
    st.error("Secrets missing! Check Streamlit Secrets.")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 STABLE CHATBOT LOGIC ---
def chat_with_gemini(prompt, uploaded_file=None):
    # Using the standard v1 production endpoint
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # Standard multimodal payload structure
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
        res = requests.post(url, headers=headers, json=payload)
        res_json = res.json()
        
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            # Better error reporting if the model refuses or key fails
            err = res_json.get('error', {}).get('message', 'Check your API quota or safety filters.')
            return f"AI Notice: {err}"
    except Exception as e:
        return f"Connection Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# --- 📟 SIDEBAR CHATBOT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    st.caption("Standard Gemini Mode")
    
    if st.button("🗑️ Clear History"):
        st.session_state.messages = []
        st.rerun()

    chat_file = st.file_uploader("Upload Image/PDF", type=["png", "jpg", "pdf", "txt"])
    
    if "messages" not in st.session_state: st.session_state.messages = []
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
        
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

# --- TAB 1: ADD ---
with tab1:
    up = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        top = st.text_input("Topic")
        nts = st.text_area("Notes")
        if st.form_submit_button("🚀 Save Mistake") and up:
            with st.spinner("Uploading..."):
                r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
                if r.status_code == 200:
                    url = r.json()["data"]["image"]["url"]
                    worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, top.title(), nts, "No"])
                    st.success("Successfully added to your bank!")

# --- TAB 2: REVIEW (SEARCH & DASHBOARD RESTORED) ---
with tab2:
    raw_data = worksheet.get_all_values()
    if len(raw_data) > 1:
        df = pd.DataFrame(raw_data[1:], columns=raw_data[0])
        # Save original row index for safe sheet updates
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
        
        # Search and Select
        cs1, cs2 = st.columns([2, 1])
        with cs1:
            search = st.text_input("🔍 Search Topic/Notes")
        with cs2:
            f_sub = st.selectbox("Subject Filter", ["All"] + sorted(list(df['Subject'].unique())))

        # Apply all filters
        f_df = df.copy()
        if 'f_date' in st.session_state:
            if st.session_state.f_date > 0:
                f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
            else:
                f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        
        if f_sub != "All":
            f_df = f_df[f_df['Subject'] == f_sub]
        if search:
            f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        if 'f_date' in st.session_state and st.button("❌ Reset Filters"):
            del st.session_state.f_date
            st.rerun()

        # Display Sorted Oldest First
        f_df = f_df.sort_values('dt', ascending=True)
        for _, row in f_df.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                cols = st.columns([1, 1, 1])
                with cols[0]:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with cols[1]:
                    mastered = row['Mastered'].strip().upper() == "YES"
                    label = "✅ Mastered" if mastered else "⬜ Done?"
                    if st.button(label, key=f"m_{row['SheetRow']}"):
                        worksheet.update_cell(row['SheetRow'], 6, "Yes" if not mastered else "No")
                        st.rerun()
                with cols[2]:
                    # Delete Confirmation
                    del_pop = st.popover("🗑️ Delete")
                    del_pop.warning("Delete permanently?")
                    if del_pop.button("Confirm", key=f"d_{row['SheetRow']}", type="primary"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("Your bank is currently empty.")

# --- TAB 3: QUIZ ---
with tab3:
    if st.button("🎯 Random Challenge"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            pend = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not pend.empty:
                p = pend.sample(1).iloc[0]
                st.image(p['ImageURL'])
                st.subheader(f"{p['Subject']}: {p['Topic']}")
            else:
                st.success("Great job! All mistakes are mastered.")

# --- TAB 4: PRINT ---
with tab4:
    st.info("Print logic ready for unmastered mistakes.")
