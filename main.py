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

# --- ⚙️ CONFIGURATION ---
IMGBB_API_KEY = "2eb6ef412c6d18c5c08e7f0f7232c042"
GEMINI_API_KEY = "AIzaSyA_rreWWeJRJEGHTGCaZUpHoV9PZCOEIKs"

genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error("Auth Error: Check your Streamlit Secrets setup."); st.stop()

creds = get_creds()
gc = gspread.authorize(creds)
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 AI FUNCTION ---
def get_ai_response(subject, topic, notes):
    prompt = f"""
    You are an elite academic tutor specializing in 11+ Super Selective exams (QE Boys, Tiffin, Henrietta Barnett) and GCSE Grade 9.
    The student made a mistake in {subject} on the topic of '{topic}'.
    Their notes for context: '{notes}'
    
    INSTRUCTIONS:
    1. Create a NEW, high-difficulty practice question based on this topic. 
    2. If it's 11+, make it a complex multi-step word problem.
    3. If it's GCSE, make it a Grade 9 algebraic or conceptual challenge.
    4. Format the output cleanly for mobile:
       - **The Challenge**
       - **Hint** (Encouraging logic, not giving it away)
       - **Step-by-Step Solution** (Hidden/at bottom)
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
    .ai-response { background-color: #f0f7ff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; font-size: 14px; color: #1e3a8a; margin-top: 10px; }
    .metric-card { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 12px; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank & AI")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD ---
with tab1:
    st.header("New Entry")
    uploaded_file = st.file_uploader("Upload image (Gallery/Files)", type=["png", "jpg", "jpeg"])
    with st.form("log_form", clear_on_submit=True):
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic (e.g., Prime Factorization)")
        notes = st.text_area("Why did you get this wrong?")
        submit = st.form_submit_button("🚀 Save Original Quality")
        
        if submit:
            if uploaded_file:
                with st.spinner("Uploading True-HD..."):
                    files = {"image": uploaded_file.getvalue()}
                    res = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files=files)
                    if res.status_code == 200:
                        hd_url = res.json()["data"]["image"]["url"]
                        if not worksheet.get_all_values():
                            worksheet.append_row(["Timestamp", "ImageURL", "Subject", "Topic", "Notes", "Mastered"])
                        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), hd_url, subject, topic.title(), notes, "No"])
                        st.success("🎉 Successfully uploaded original resolution!")
                    else:
                        st.error("Upload failed. Check ImgBB API key.")
            else:
                st.warning("Please upload an image first.")

# --- TAB 2: INTERACTIVE REVIEW ---
with tab2:
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            df['dt_obj'] = pd.to_datetime(df['Timestamp'], format="%Y-%m-%d %H:%M")
            now = datetime.now()
            
            # Dashboard
            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f'<div class="metric-card"><small>7 DAYS</small><br><b>{len(df[df["dt_obj"] > (now - timedelta(days=7))])}</b></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="metric-card"><small>14 DAYS</small><br><b>{len(df[df["dt_obj"] > (now - timedelta(days=14))])}</b></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="metric-card"><small>PENDING</small><br><b style="color:red;">{len(df[df["Mastered"].str.upper() != "YES"])}</b></div>', unsafe_allow_html=True)

            st.divider()
            
            f_sub = st.selectbox("Filter Subject:", ["All"] + sorted(list(df['Subject'].unique())))
            filtered_df = df.copy()
            if f_sub != "All": filtered_df = filtered_df[filtered_df['Subject'] == f_sub]
            filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]

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
                            with st.spinner("AI Tutor is thinking..."):
                                st.session_state[f"ai_res_{index}"] = get_ai_response(row['Subject'], row['Topic'], row['Notes'])
                    with col3:
                        if st.button("✅", key=f"done_{index}"):
                            worksheet.update_cell(actual_sheet_row, 6, "Yes"); st.rerun()

                    if f"ai_res_{index}" in st.session_state:
                        st.markdown(f'<div class="ai-response">{st.session_state[f"ai_res_{index}"]}</div>', unsafe_allow_html=True)
        else:
            st.info("Your mistake bank is currently empty.")
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
                with st.expander("Show My Original Notes"): st.write(pick['Notes'])
                if st.button("🪄 AI Extension"):
                    with st.spinner("Generating fresh exam problem..."):
                        q = get_ai_response(pick['Subject'], pick['Topic'], pick['Notes'])
                        st.markdown(f'<div class="ai-response">{q}</div>', unsafe_allow_html=True)

# --- TAB 4: PRINT ---
with tab4:
    st.header("🖨️ PDF Generation")
    if st.button("📄 Build High-Res Revision PDF"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_pdf = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            to_print = df_pdf[df_pdf['Mastered'].str.upper() != "YES"]
            if not to_print.empty:
                with st.spinner("Fetching HD images..."):
                    pdf = FPDF()
                    for _, row in to_print.iterrows():
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 14)
                        pdf.cell(0, 10, f"{row['Subject']} - {row['Topic']}", ln=True, align='C')
                        img_resp = requests.get(row['ImageURL'])
                        with open("temp.jpg", "wb") as f: f.write(img_resp.content)
                        pdf.image("temp.jpg", x=10, y=30, w=190)
                    st.download_button("📥 Download PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="revision.pdf")
