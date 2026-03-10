import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
import base64
from io import BytesIO
from PIL import Image

# --- 🛡️ SECURE AUTHENTICATION ---
def get_creds():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        raw_key = creds_dict["private_key"]
        header, footer = "-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"
        clean_key = raw_key.replace(header, "").replace(footer, "").replace("\n", "").replace(" ", "").strip()
        creds_dict["private_key"] = f"{header}\n{clean_key}\n{footer}"
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error(f"Secret Error: {e}")
        st.stop()

creds = get_creds()
gc = gspread.authorize(creds)

# Open Sheet
try:
    sh = gc.open("Study Mistake Log")
    worksheet = sh.worksheet("Mistakes")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

# --- 🎨 APP INTERFACE ---
st.set_page_config(page_title="11+ Mistake Tracker", layout="wide")
st.title("📚 Permanent Error Bank")

with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Question Image", type=["png", "jpg", "jpeg"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="Preview", use_container_width=True)
    
    subject = st.selectbox("Subject", ['Maths', 'Verbal Reasoning', 'Non-Verbal', 'English', 'SPAG'])
    topic_tag = st.text_input("Topic")
    notes = st.text_area("Notes")

    if st.button("🚀 Save Mistake"):
        if uploaded_file:
            with st.spinner("Processing image..."):
                try:
                    # 1. Convert Image and Handle Transparency (RGBA to RGB)
                    img = Image.open(uploaded_file)
                    
                    # --- THE FIX IS HERE ---
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    # -----------------------

                    # Resize to keep the Google Sheet from hitting the cell limit (50,000 chars)
                    img.thumbnail((600, 600)) 
                    buffered = BytesIO()
                    img.save(buffered, format="JPEG", quality=60) # Quality 60 saves space
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    image_data_link = f"data:image/jpeg;base64,{img_str}"

                    # 2. Save to Google Sheet
                    new_row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        image_data_link, 
                        subject,
                        topic_tag.title(),
                        notes
                    ]
                    worksheet.append_row(new_row)
                    st.success("✅ Saved Successfully!")
                    st.balloons()
                except Exception as err:
                    st.error(f"Processing Error: {err}")
        else:
            st.error("Please upload an image first!")

# --- 🔍 DISPLAY DATA ---
st.subheader("Your Mistake Log")
try:
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        
        # Display table with clickable links
        st.dataframe(
            df, 
            column_config={
                "Image": st.column_config.LinkColumn("View Question", display_text="View Image 🖼️")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No mistakes logged yet.")
except Exception as read_error:
    st.error(f"Read error: {read_error}")
