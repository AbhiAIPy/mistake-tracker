import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
import requests
from io import BytesIO
from PIL import Image
import random

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
st.set_page_config(page_title="11+ Bank", layout="centered")
st.markdown("""
<style> 
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    div[data-testid="stExpander"] { border: 1px solid #ddd; border-radius: 10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank")

tab1, tab2, tab3 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz"])

# --- TAB 1: ADD MISTAKE ---
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
                with st.spinner("Processing..."):
                    img = Image.open(uploaded_file)
                    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                    img.thumbnail((1600, 1600)) 
                    buf = BytesIO()
                    img.save(buf, format="JPEG", quality=80)
                    
                    res = requests.post("https://api.imgbb.com/1/upload", 
                                       data={"key": IMGBB_API_KEY}, 
                                       files={"image": buf.getvalue()})
                    
                    if res.status_code == 200:
                        url = res.json()["data"]["url"]
                        
                        # Ensure headers exist
                        if not worksheet.get_all_values():
                            worksheet.append_row(["Timestamp", "ImageURL", "Subject", "Topic", "Notes", "Mastered"])

                        worksheet.append_row([
                            datetime.now().strftime("%Y-%m-%d %H:%M"), 
                            url, subject, topic.title(), notes, "No"
                        ])
                        st.success("Saved!")
                        st.rerun()
            else:
                st.error("Please provide an image!")

# --- TAB 2: REVIEW CARDS ---
with tab2:
    try:
        # SAFER DATA LOADING: Get all rows as a list of lists
        all_rows = worksheet.get_all_values()
        
        if len(all_rows) > 1:
            # Convert to DataFrame using the first row as headers
            df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            
            # Mobile Filters
            col_a, col_b = st.columns(2)
            with col_a:
                f_sub = st.selectbox("Filter:", ["All"] + sorted(list(df['Subject'].unique())))
            with col_b:
                show_mastered = st.toggle("Show Mastered", value=False)

            # Filtering logic
            filtered_df = df.copy()
            if f_sub != "All":
                filtered_df = filtered_df[filtered_df['Subject'] == f_sub]
            if not show_mastered:
                filtered_df = filtered_df[filtered_df['Mastered'].str.upper() != "YES"]

            for index, row in filtered_df.iloc[::-1].iterrows():
                # Re-calculate the actual row in Google Sheets (header + 1-based index)
                # Since we inverted the display, we find the index from the original DF
                actual_sheet_row = df.index[df['Timestamp'] == row['Timestamp']].tolist()[0] + 2

                with st.container(border=True):
                    st.subheader(f"{row['Subject']}: {row['Topic']}")
                    st.image(row['ImageURL'], use_container_width=True)
                    if row['Notes']:
                        st.info(f"💡 {row['Notes']}")
                    
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
            st.info("No data found.")
    except Exception as e:
        st.error(f"Display Error: {e}")

# --- TAB 3: QUIZ ---
with tab3:
    st.header("Quick Quiz")
    if st.button("🎯 Random Question"):
        all_rows = worksheet.get_all_values()
        if len(all_rows) > 1:
            df_quiz = pd.DataFrame(all_rows[1:], columns=all_rows[0])
            unsolved = df_quiz[df_quiz['Mastered'].str.upper() != "YES"]
            
            if not unsolved.empty:
                pick = unsolved.sample(n=1).iloc[0]
                st.image(pick['ImageURL'], use_container_width=True)
                st.write(f"**Topic:** {pick['Topic']}")
                with st.expander("Reveal Notes"):
                    st.write(pick['Notes'])
            else:
                st.warning("No new questions left!")
