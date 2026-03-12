import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
import json
from fpdf import FPDF

# --- ⚙️ CONFIGURATION (SECURE) ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Secrets missing! Add IMGBB_API_KEY and GEMINI_API_KEY to Streamlit Secrets.")
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

# --- 🤖 AI VISION FUNCTION ---
def get_ai_response(subject, topic, notes, image_url):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        # 1. Download the image from ImgBB and encode to Base64
        img_data = requests.get(image_url).content
        base64_image = base64.b64encode(img_data).decode('utf-8')
        
        headers = {'Content-Type': 'application/json'}
        
        # 2. Construct Multimodal Prompt (Text + Image)
        data = {
            "contents": [{
                "parts": [
                    {"text": f"You are an expert tutor. Look at this {subject} question about {topic}. Explain the solution step-by-step based on the image. Also, provide one similar practice question. Student Notes: {notes}"},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }
                    }
                ]
            }]
        }

        response = requests.post(url, headers=headers, json=data)
        res_json = response.json()
        
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return "AI could not process the image. Please try again."
    except Exception as e:
        return f"Vision Error: {str(e)}"

# --- 🎨 MOBILE UI SETUP ---
st.set_page_config(page_title="11+ AI Master Bank", layout="centered")
st.markdown("""
<style> 
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    .ai-response { background-color: #f0f7ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; font-size: 14px; margin-top:10px; }
    .date-label { font-size: 11px; color: #94a3b8; font-style: italic; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank & AI")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD (No changes here) ---
with tab1:
    st.header("New Entry")
    uploaded_file = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])
    with st.form("log_form", clear_on_submit=True):
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Why did you get this wrong?")
        submit = st.form_submit_button("🚀 Save Original Quality")
        
        if submit and uploaded_file:
            with st.spinner("Uploading..."):
                files = {"image": uploaded_file.getvalue()}
                res = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files=files)
                if res.status_code == 200:
                    hd_url = res.json()["data"]["image"]["url"]
                    worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), hd_url, subject, topic.title(), notes, "No"])
                    st.success("🎉 Saved!")

# --- TAB 2: REVIEW (Vision & Delete Fix) ---
with tab2:
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            df['dt_obj'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M")
            
            # Dashboard logic (7/14/Pending)
            st.caption("Quick Filters:")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button(f"📅 7 Days", key="dash_7"): st.session_state.filter_date = 7
            with c2:
                if st.button(f"🗓️ 14 Days", key="dash_14"): st.session_state.filter_date = 14
            with c3:
                if st.button(f"⏳ Pending", key="dash_pend"): st.session_state.filter_date = 0

            filtered_df = df.copy()
            if 'filter_date' in st.session_state:
                if st.session_state.filter_date > 0:
                    filtered_df = filtered_df[filtered_df['dt_obj'] > (datetime.now() - timedelta(days=st.session_state.filter_date))]
                else:
                    filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]

            filtered_df = filtered_df.sort_values(by='dt_obj', ascending=True)

            for index, row in filtered_df.iterrows():
                actual_sheet_row = df.index[df['Timestamp'] == row['Timestamp']].tolist()[0] + 2
                with st.container(border=True):
                    st.markdown(f"<div class='date-label'>📅 {row['Timestamp']}</div>", unsafe_allow_html=True)
                    st.write(f"**{row['Subject']}**: {row['Topic']}")
                    
                    col1, col2, col3, col4 = st.columns([1,1,1,1])
                    with col1:
                        v = st.popover("🖼️")
                        v.image(row['ImageURL'])
                    with col2:
                        if st.button("🪄 AI", key=f"ai_{index}"):
                            with st.spinner("AI is reading..."):
                                st.session_state[f"ai_res_{index}"] = get_ai_response(row['Subject'], row['Topic'], row['Notes'], row['ImageURL'])
                    with col3:
                        btn_label = "Reset" if row['Mastered'].upper() == "YES" else "Check"
                        if st.button(btn_label, key=f"done_{index}"):
                            new_val = "No" if row['Mastered'].upper() == "YES" else "Yes"
                            worksheet.update_cell(actual_sheet_row, 6, new_val)
                            st.rerun()
                    with col4:
                        # --- DELETE WITH PROMPT ---
                        del_pop = st.popover("🗑️")
                        del_pop.warning("Are you sure?")
                        if del_pop.button("Confirm Delete", key=f"del_conf_{index}"):
                            worksheet.delete_rows(actual_sheet_row)
                            st.rerun()

                    if f"ai_res_{index}" in st.session_state:
                        st.markdown(f'<div class="ai-response">{st.session_state[f"ai_res_{index}"]}</div>', unsafe_allow_html=True)
        else:
            st.info("No records yet.")
    except Exception as e:
        st.error(f"Review Error: {e}")

# (Quiz and Print tabs remain unchanged)
with tab3:
    st.header("Random Revision")
    if st.button("🎯 Get Random Challenge"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_q = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            pick = df_q[df_q['Mastered'].str.upper() != "YES"].sample(n=1).iloc[0]
            st.image(pick['ImageURL'])
            st.subheader(f"{pick['Subject']}: {pick['Topic']}")

with tab4:
    if st.button("📄 Build Revision PDF"):
        st.write("Generating...")
        # (Original PDF Logic here)
