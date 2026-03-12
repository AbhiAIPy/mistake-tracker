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
st.set_page_config(page_title="11+ Bank", layout="centered") # Centered is better for mobile
st.title("🧠 11+ Mistake Bank")

# Use tabs for a clean mobile UI
tab1, tab2, tab3 = st.tabs(["➕ Log", "🔍 Review", "🎲 Quiz"])

# --- TAB 1: QUICK LOG ---
with tab1:
    with st.form("quick_log", clear_on_submit=True):
        st.header("Capture Mistake")
        
        # Choice between Camera or Gallery
        source = st.radio("Photo Source:", ["Camera", "Gallery"], horizontal=True)
        if source == "Camera":
            uploaded_file = st.camera_input("Take a photo")
        else:
            uploaded_file = st.file_uploader("Pick from Gallery", type=["png", "jpg", "jpeg"])
        
        subject = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic_tag = st.text_input("Topic")
        notes = st.text_area("Why was this wrong?")
        
        submitted = st.form_submit_button("🚀 Save to Cloud")
        
        if submitted and uploaded_file:
            with st.spinner("Saving..."):
                img = Image.open(uploaded_file)
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                img.thumbnail((1600, 1600)) 
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=80)
                
                response = requests.post("https://api.imgbb.com/1/upload", 
                                         data={"key": IMGBB_API_KEY}, 
                                         files={"image": buffer.getvalue()})
                
                if response.status_code == 200:
                    image_url = response.json()["data"]["url"]
                    worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), image_url, subject, topic_tag.title(), notes, "No"])
                    st.success("Saved!")
                else:
                    st.error("Upload Error")

# --- TAB 2: EASY REVIEW ---
with tab2:
    try:
        data = worksheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            
            # Simplified Mobile Filters
            sub_filter = st.selectbox("Filter:", ["All Subjects"] + list(df['Subject'].unique()))
            if sub_filter != "All Subjects":
                df = df[df['Subject'] == sub_filter]
            
            # Use a list of "Cards" instead of a wide table for mobile
            for index, row in df.iloc[::-1].iterrows(): # Show newest first
                with st.expander(f"{row['Subject']} - {row['Topic']}"):
                    st.image(row['ImageURL'], use_container_width=True)
                    st.write(f"**Notes:** {row['Notes']}")
                    st.caption(f"Logged: {row['Timestamp']}")
                    
                    if st.button("Delete", key=f"del_{index}"):
                        worksheet.delete_rows(index + 2) # +2 for header and 0-index
                        st.rerun()
        else:
            st.info("No data found.")
    except:
        st.error("Error loading data.")

# --- TAB 3: RANDOM QUIZ ---
with tab3:
    st.header("Daily Challenge")
    if st.button("🎯 Pick a Random Question"):
        data = worksheet.get_all_records()
        if data:
            pick = random.choice(data)
            st.image(pick['ImageURL'], use_container_width=True)
            st.info(f"Topic: {pick['Topic']}")
            with st.expander("See My Notes"):
                st.write(pick['Notes'])
        else:
            st.warning("No questions available!")
