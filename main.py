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
    st.error("Secrets missing! Add IMGBB_API_KEY and GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 FIXED AI VISION FUNCTION ---
def get_ai_response(subject, topic, notes, image_url):
    # Using the v1beta endpoint which is best for Multimodal (Vision)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        # 1. Get the image from the URL and convert to Base64
        response = requests.get(image_url)
        if response.status_code != 200:
            return "Error: Could not retrieve image from storage."
        
        image_base64 = base64.b64encode(response.content).decode('utf-8')
        
        # 2. Prepare the payload with vision data
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"You are a professional 11+ and GCSE tutor. Analyze the uploaded image which is a {subject} question about {topic}. Explain the solution step-by-step. Then, provide one new similar practice question based on what you see. Student Notes: {notes}"},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }
            ]
        }

        # 3. Request to Gemini
        res = requests.post(url, headers=headers, json=payload)
        res_json = res.json()
        
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"AI Refused: {res_json.get('error', {}).get('message', 'The model could not read this specific image.')}"
            
    except Exception as e:
        return f"Vision Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ AI Master Bank", layout="centered")
st.markdown("""
<style> 
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    .ai-response { background-color: #f0f7ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; font-size: 14px; margin-top: 10px;}
    .date-label { font-size: 11px; color: #94a3b8; font-style: italic; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank & AI")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD ---
with tab1:
    uploaded_file = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])
    with st.form("log_form", clear_on_submit=True):
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Why did you get this wrong?")
        submit = st.form_submit_button("🚀 Save Original Quality")
        
        if submit and uploaded_file:
            with st.spinner("Uploading..."):
                res = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": uploaded_file.getvalue()})
                if res.status_code == 200:
                    hd_url = res.json()["data"]["image"]["url"]
                    worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), hd_url, subject, topic.title(), notes, "No"])
                    st.success("🎉 Saved!")

# --- TAB 2: REVIEW ---
with tab2:
    all_rows = worksheet.get_all_values()
    if len(all_rows) > 1:
        df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        df['dt_obj'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M")
        
        # Dashboard Filters
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📅 7 Days", key="d7"): st.session_state.f_date = 7
        with c2:
            if st.button("🗓️ 14 Days", key="d14"): st.session_state.f_date = 14
        with c3:
            if st.button("⏳ Pending", key="dpend"): st.session_state.f_date = 0

        filtered_df = df.copy()
        if 'f_date' in st.session_state:
            if st.session_state.f_date > 0:
                filtered_df = filtered_df[filtered_df['dt_obj'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
            else:
                filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]

        # SORT ASCENDING
        filtered_df = filtered_df.sort_values(by='dt_obj', ascending=True)

        for index, row in filtered_df.iterrows():
            actual_sheet_row = df.index[df['Timestamp'] == row['Timestamp']].tolist()[0] + 2
            with st.container(border=True):
                st.markdown(f"<div class='date-label'>📅 {row['Timestamp']}</div>", unsafe_allow_html=True)
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                
                col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
                with col1:
                    v = st.popover("🖼️")
                    v.image(row['ImageURL'])
                with col2:
                    if st.button("🪄 AI", key=f"ai_{index}"):
                        with st.spinner("Reading Image..."):
                            st.session_state[f"res_{index}"] = get_ai_response(row['Subject'], row['Topic'], row['Notes'], row['ImageURL'])
                with col3:
                    label = "Reset" if row['Mastered'].upper() == "YES" else "Check"
                    if st.button(label, key=f"chk_{index}"):
                        new_stat = "No" if row['Mastered'].upper() == "YES" else "Yes"
                        worksheet.update_cell(actual_sheet_row, 6, new_stat)
                        st.rerun()
                with col4:
                    # DELETE WITH "ARE YOU SURE" PROMPT
                    del_pop = st.popover("🗑️")
                    del_pop.warning("Are you sure?")
                    if del_pop.button("Confirm Delete", key=f"del_{index}", type="primary"):
                        worksheet.delete_rows(actual_sheet_row)
                        st.rerun()

                if f"res_{index}" in st.session_state:
                    st.markdown(f'<div class="ai-response">{st.session_state[f"res_{index}"]}</div>', unsafe_allow_html=True)
    else:
        st.info("No records yet.")

# --- TAB 3: QUIZ & TAB 4: PRINT ---
with tab3:
    if st.button("🎯 Get Random Challenge"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_q = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            pick = df_q[df_q['Mastered'].str.upper() != "YES"].sample(n=1).iloc[0]
            st.image(pick['ImageURL'])
            st.subheader(f"{pick['Subject']}: {pick['Topic']}")
            if st.button("🪄 AI Help", key="quiz_ai"):
                st.write(get_ai_response(pick['Subject'], pick['Topic'], pick['Notes'], pick['ImageURL']))

with tab4:
    if st.button("📄 Build PDF"):
        # (PDF generation logic as per your working version)
        st.write("Generating PDF...")
