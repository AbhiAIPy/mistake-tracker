import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
import requests
from io import BytesIO
from PIL import Image
import random
from fpdf import FPDF

# --- ⚙️ CONFIGURATION ---
IMGBB_API_KEY = "2eb6ef412c6d18c5c08e7f0f7232c042"

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error("Auth Error"); st.stop()

creds = get_creds()
gc = gspread.authorize(creds)
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🎨 MOBILE UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="centered")
st.markdown("""
<style> 
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    /* Visual separation for entries */
    div.stContainer {
        border: 1px solid #e6e9ef;
        padding: 10px;
        border-radius: 15px;
        margin-bottom: 15px;
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD MISTAKE (WITH STATUS FEEDBACK) ---
with tab1:
    st.header("New Entry")
    upload_mode = st.radio("Source:", ["Gallery/File", "Use Camera"], horizontal=True)
    
    uploaded_file = None
    if upload_mode == "Use Camera":
        uploaded_file = st.camera_input("Snap a photo")
    else:
        uploaded_file = st.file_uploader("Upload from gallery", type=["png", "jpg", "jpeg"])

    with st.form("log_form", clear_on_submit=True):
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Notes")
        submit = st.form_submit_button("🚀 Save Original Quality")

        if submit:
            if uploaded_file:
                # Create a placeholder for the status message
                status_box = st.empty()
                with st.spinner("Uploading to cloud..."):
                    try:
                        # Raw bytes upload for original quality
                        files = {"image": uploaded_file.getvalue()}
                        res = requests.post("https://api.imgbb.com/1/upload", 
                                           data={"key": IMGBB_API_KEY}, 
                                           files=files)
                        
                        if res.status_code == 200:
                            url = res.json()["data"]["url"]
                            if not worksheet.get_all_values():
                                worksheet.append_row(["Timestamp", "ImageURL", "Subject", "Topic", "Notes", "Mastered"])
                            
                            worksheet.append_row([
                                datetime.now().strftime("%Y-%m-%d %H:%M"), 
                                url, subject, topic.title(), notes, "No"
                            ])
                            status_box.success("🎉 Upload Successful! Mistake saved to your bank.")
                        else:
                            status_box.error(f"❌ Upload Failed. (Error: {res.status_code})")
                    except Exception as err:
                        status_box.error(f"⚠️ Connection Error: {err}")
            else:
                st.warning("⚠️ Please provide an image before saving.")

# --- TAB 2: REVIEW CARDS (ICON & EXPANDERS) ---
with tab2:
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            
            f_sub = st.selectbox("Filter:", ["All"] + sorted(list(df['Subject'].unique())))
            show_mastered = st.toggle("Show Mastered", value=False)

            filtered_df = df.copy()
            if f_sub != "All":
                filtered_df = filtered_df[filtered_df['Subject'] == f_sub]
            if not show_mastered:
                filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]

            for index, row in filtered_df.iloc[::-1].iterrows():
                actual_sheet_row = df.index[df['Timestamp'] == row['Timestamp']].tolist()[0] + 2
                
                with st.container():
                    st.write(f"**{row['Subject']}**: {row['Topic']}")
                    
                    # Image hidden behind expander (acts as a "Clickable Icon")
                    with st.expander("🖼️ View Image Detail"):
                        st.image(row['ImageURL'], use_container_width=True)
                        st.markdown(f"[🔗 Open Original File]({row['ImageURL']})")
                    
                    if row['Notes']:
                        st.caption(f"💡 {row['Notes']}")
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("✅ Mastered", key=f"win_{index}"):
                            worksheet.update_cell(actual_sheet_row, 6, "Yes")
                            st.rerun()
                    with b2:
                        if st.button("🗑️ Delete", key=f"del_{index}"):
                            worksheet.delete_rows(actual_sheet_row)
                            st.rerun()
        else:
            st.info("No mistakes recorded yet.")
    except Exception as e:
        st.error(f"Data Error: {e}")

# --- TAB 3: QUIZ ---
with tab3:
    st.header("Random Revision")
    if st.button("🎲 Get a Challenge"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_q = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            unsolved = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not unsolved.empty:
                pick = unsolved.sample(n=1).iloc[0]
                st.image(pick['ImageURL'], use_container_width=True)
                st.subheader(f"{pick['Subject']}: {pick['Topic']}")
                with st.expander("Check your notes"):
                    st.write(pick['Notes'])

# --- TAB 4: PRINT ---
with tab4:
    st.header("🖨️ Export PDF")
    if st.button("📄 Generate PDF of Unsolved"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_pdf = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            to_print = df_pdf[df_pdf['Mastered'].str.upper() != "YES"]
            if not to_print.empty:
                with st.spinner("Preparing high-res PDF..."):
                    pdf = FPDF()
                    for _, row in to_print.iterrows():
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 14)
                        pdf.cell(0, 10, f"{row['Subject']} - {row['Topic']}", ln=True, align='C')
                        # Add high-res image to PDF
                        img_resp = requests.get(row['ImageURL'])
                        with open("temp.jpg", "wb") as f: f.write(img_resp.content)
                        pdf.image("temp.jpg", x=10, y=30, w=190)
                    st.download_button("📥 Download PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="revision_sheet.pdf")
