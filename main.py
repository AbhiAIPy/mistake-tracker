import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
from io import BytesIO
import random
from fpdf import FPDF
import google.generativeai as genai

# --- ⚙️ CONFIGURATION (SECURE) ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
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

# --- 🤖 AI FUNCTION ---
def get_ai_response(subject, topic, notes):
    prompt = f"""
    You are an elite academic tutor specializing in 11+ Super Selective exams and GCSE Grade 9.
    The student made a mistake in {subject} on the topic of '{topic}'.
    Their notes: '{notes}'
    
    Format the output cleanly for mobile:
    1. **The Challenge**: A high-difficulty exam style question.
    2. **Hint**: Encouraging logic.
    3. **Solution**: Step-by-step working.
    """
    try:
        response = ai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Logic Error: {str(e)}"

# --- 🎨 MOBILE UI SETUP ---
st.set_page_config(page_title="11+ AI Master Bank", layout="centered")
st.markdown("""
<style> 
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    .ai-response { background-color: #f0f7ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; font-size: 14px; }
    .metric-card { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 12px; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank & AI")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD ---
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
                    st.success("🎉 Saved to Cloud!")

# --- TAB 2: REVIEW ---
with tab2:
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            df['dt_obj'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M")
            now = datetime.now()
            
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f'<div class="metric-card"><small>7 DAYS</small><br><b>{len(df[df["dt_obj"] > (now - timedelta(days=7))])}</b></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><small>14 DAYS</small><br><b>{len(df[df["dt_obj"] > (now - timedelta(days=14))])}</b></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><small>PENDING</small><br><b style="color:red;">{len(df[df["Mastered"].str.upper() != "YES"])}</b></div>', unsafe_allow_html=True)

            st.divider()
            f_sub = st.selectbox("Filter Subject:", ["All"] + sorted(list(df['Subject'].unique())))
            filtered_df = df[df['Mastered'].str.upper() != "YES"]
            if f_sub != "All": filtered_df = filtered_df[filtered_df['Subject'] == f_sub]

            for index, row in filtered_df.iloc[::-1].iterrows():
                actual_sheet_row = df.index[df['Timestamp'] == row['Timestamp']].tolist()[0] + 2
                with st.container(border=True):
                    st.write(f"**{row['Subject']}**: {row['Topic']}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        v = st.popover("🖼️ View")
                        v.image(row['ImageURL'], use_container_width=True)
                    with col2:
                        if st.button("🪄 AI", key=f"ai_{index}"):
                            with st.spinner("Thinking..."):
                                st.session_state[f"ai_res_{index}"] = get_ai_response(row['Subject'], row['Topic'], row['Notes'])
                    with col3:
                        if st.button("✅", key=f"done_{index}"):
                            worksheet.update_cell(actual_sheet_row, 6, "Yes"); st.rerun()

                    if f"ai_res_{index}" in st.session_state:
                        st.markdown(f'<div class="ai-response">{st.session_state[f"ai_res_{index}"]}</div>', unsafe_allow_html=True)
        else:
            st.info("No records yet.")
    except Exception as e:
        st.error(f"Review Error: {e}")

# --- TAB 3: QUIZ ---
with tab3:
    st.header("Random Revision")
    if st.button("🎯 Get Random Challenge"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_q = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            unsolved = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not unsolved.empty:
                pick = unsolved.sample(n=1).iloc[0]
                st.image(pick['ImageURL'], use_container_width=True)
                st.subheader(f"{pick['Subject']}: {pick['Topic']}")
                if st.button("🪄 AI Extension"):
                    st.write(get_ai_response(pick['Subject'], pick['Topic'], pick['Notes']))

# --- TAB 4: PRINT ---
with tab4:
    if st.button("📄 Build Revision PDF"):
        all_rows = worksheet.get_all_values()
        df_pdf = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        to_print = df_pdf[df_pdf['Mastered'].str.upper() != "YES"]
        pdf = FPDF()
        for _, row in to_print.iterrows():
            pdf.add_page()
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, f"{row['Subject']} - {row['Topic']}", ln=True, align='C')
            img_resp = requests.get(row['ImageURL'])
            with open("temp.jpg", "wb") as f: f.write(img_resp.content)
            pdf.image("temp.jpg", x=10, y=30, w=190)
        st.download_button("📥 Download PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="revision.pdf")
