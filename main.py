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
    div[data-testid="stExpander"] { border: 1px solid #ddd; border-radius: 10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank")

tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

# --- TAB 1: ADD MISTAKE (MAX QUALITY) ---
with tab1:
    st.header("New Entry")
    upload_mode = st.radio("Source:", ["Gallery/File", "Use Camera"], horizontal=True)
    
    uploaded_file = None
    if upload_mode == "Use Camera":
        uploaded_file = st.camera_input("Snap a photo")
    else:
        uploaded_file = st.file_uploader("Upload from gallery", type=["png", "jpg", "jpeg"])

    with st.form("log_form"):
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Notes")
        submit = st.form_submit_button("🚀 Save Mistake")

        if submit:
            if uploaded_file:
                with st.spinner("Processing Max Quality..."):
                    img = Image.open(uploaded_file)
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    
                    # MAX QUALITY SETTINGS
                    img.thumbnail((2500, 2500)) 
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=95) 
                    
                    res = requests.post("https://api.imgbb.com/1/upload", 
                                       data={"key": IMGBB_API_KEY}, 
                                       files={"image": buf.getvalue()})
                    
                    if res.status_code == 200:
                        url = res.json()["data"]["url"]
                        if not worksheet.get_all_values():
                            worksheet.append_row(["Timestamp", "ImageURL", "Subject", "Topic", "Notes", "Mastered"])
                        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, subject, topic.title(), notes, "No"])
                        st.success("Saved at High Quality!")
                        st.rerun()
            else:
                st.error("Missing image!")

# --- TAB 2: REVIEW CARDS ---
with tab2:
    try:
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            col_a, col_b = st.columns(2)
            with col_a:
                f_sub = st.selectbox("Filter:", ["All"] + sorted(list(df['Subject'].unique())))
            with col_b:
                show_mastered = st.toggle("Show Mastered", value=False)

            filtered_df = df.copy()
            if f_sub != "All":
                filtered_df = filtered_df[filtered_df['Subject'] == f_sub]
            if not show_mastered:
                filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]

            for index, row in filtered_df.iloc[::-1].iterrows():
                actual_sheet_row = df.index[df['Timestamp'] == row['Timestamp']].tolist()[0] + 2
                with st.container(border=True):
                    st.subheader(f"{row['Subject']}: {row['Topic']}")
                    st.image(row['ImageURL'], use_container_width=True)
                    if row['Notes']: st.info(f"💡 {row['Notes']}")
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
            st.info("Empty bank.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- TAB 3: QUIZ ---
with tab3:
    st.header("Random Challenge")
    if st.button("🎯 Give me a Question"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_q = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            unsolved = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not unsolved.empty:
                pick = unsolved.sample(n=1).iloc[0]
                st.image(pick['ImageURL'], use_container_width=True)
                st.write(f"**Topic:** {pick['Topic']}")
                with st.expander("Show Notes"): st.write(pick['Notes'])
            else:
                st.warning("No new questions!")

# --- TAB 4: PDF PRINTING ---
with tab4:
    st.header("🖨️ Create Practice Sheet")
    st.write("Generate a PDF of all questions you haven't mastered yet.")
    
    if st.button("📄 Generate Revision PDF"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_pdf = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            to_print = df_pdf[df_pdf['Mastered'].str.upper() != "YES"]
            
            if not to_print.empty:
                with st.spinner("Building PDF..."):
                    pdf = FPDF()
                    for _, row in to_print.iterrows():
                        pdf.add_page()
                        pdf.set_font("Arial", 'B', 16)
                        pdf.cell(0, 10, f"{row['Subject']} - {row['Topic']}", ln=True, align='C')
                        pdf.set_font("Arial", size=10)
                        pdf.cell(0, 10, f"Logged: {row['Timestamp']}", ln=True, align='C')
                        
                        # Fetch image from URL
                        img_resp = requests.get(row['ImageURL'])
                        img_data = BytesIO(img_resp.content)
                        
                        # Temporary save to local for FPDF
                        with open("temp_img.jpg", "wb") as f:
                            f.write(img_data.getbuffer())
                        
                        # Add image to PDF (Scale to fit page width)
                        pdf.image("temp_img.jpg", x=10, y=30, w=190)
                    
                    pdf_output = pdf.output(dest='S').encode('latin-1')
                    st.download_button(label="📥 Download PDF", data=pdf_output, file_name="11plus_revision.pdf", mime="application/pdf")
            else:
                st.warning("No unmastered questions to print!")
        else:
            st.error("No data available.")
