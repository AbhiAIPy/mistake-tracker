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
st.markdown("""<style> .stButton>button { width: 100%; border-radius: 10px; height: 3em; } </style>""", unsafe_allow_html=True)

st.title("🧠 11+ Mistake Bank")

tab1, tab2, tab3 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz"])

# --- TAB 1: ADD MISTAKE (Camera on Demand) ---
with tab1:
    st.header("New Entry")
    
    # Selection for input type
    upload_mode = st.radio("Choose source:", ["Gallery/File", "Use Camera"], horizontal=True)
    
    uploaded_file = None
    if upload_mode == "Use Camera":
        # Camera only appears if this mode is selected
        uploaded_file = st.camera_input("Snap a photo")
    else:
        uploaded_file = st.file_uploader("Upload from gallery", type=["png", "jpg", "jpeg"])

    with st.form("log_form"):
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic (e.g. Ratios)")
        notes = st.text_area("Notes / Reminders")
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
                        # Adding "No" as the default for "Mastered"
                        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, subject, topic.title(), notes, "No"])
                        st.success("Saved!")
                        st.rerun()
            else:
                st.error("Please provide an image!")

# --- TAB 2: REVIEW CARDS ---
with tab2:
    try:
        data = worksheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            
            col_a, col_b = st.columns(2)
            with col_a:
                f_sub = st.selectbox("Subject:", ["All"] + list(df['Subject'].unique()))
            with col_b:
                # Filter to see only things you haven't mastered yet
                show_mastered = st.toggle("Show Mastered", value=False)

            # Filtering logic
            if f_sub != "All":
                df = df[df['Subject'] == f_sub]
            if not show_mastered:
                df = df[df['Mastered'].astype(str).str.upper() != "YES"]

            for index, row in df.iloc[::-1].iterrows():
                with st.container(border=True):
                    st.subheader(f"{row['Subject']}: {row['Topic']}")
                    st.image(row['ImageURL'], use_container_width=True)
                    if row['Notes']:
                        st.info(f"💡 {row['Notes']}")
                    
                    # Mobile friendly buttons in columns
                    btn1, btn2 = st.columns(2)
                    with btn1:
                        if st.button("✅ Mastered", key=f"win_{index}"):
                            # Update the 'Mastered' column (column 6)
                            worksheet.update_cell(index + 2, 6, "Yes")
                            st.rerun()
                    with btn2:
                        if st.button("🗑️ Delete", key=f"del_{index}"):
                            worksheet.delete_rows(index + 2)
                            st.rerun()
        else:
            st.info("Your bank is empty.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- TAB 3: RANDOM CHALLENGE ---
with tab3:
    st.header("Random Revision")
    if st.button("🎯 Give me a Challenge"):
        data = worksheet.get_all_records()
        # Filter out mastered questions for the quiz
        unsolved = [d for d in data if str(d.get('Mastered')).upper() != "YES"]
        
        if unsolved:
            pick = random.choice(unsolved)
            st.image(pick['ImageURL'], use_container_width=True)
            st.write(f"**Subject:** {pick['Subject']} | **Topic:** {pick['Topic']}")
            with st.expander("Reveal Notes"):
                st.write(pick['Notes'])
        else:
            st.warning("No unmastered questions left! Add more or reset some.")
