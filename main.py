import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from datetime import datetime
import pandas as pd
import io

# --- ⚙️ CONFIGURATION ---
# Your verified Folder ID
DRIVE_FOLDER_ID = "1AcX7WW-9QFPlldEidgo4U6y-6YqMkNjv" 

# --- 🛡️ SECURE AUTHENTICATION ---
def get_creds():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        raw_key = creds_dict["private_key"]
        header, footer = "-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"
        # Standardize key format for the cryptography library
        clean_key = raw_key.replace(header, "").replace(footer, "").replace("\n", "").replace(" ", "").strip()
        creds_dict["private_key"] = f"{header}\n{clean_key}\n{footer}"
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error(f"Secret Error: {e}")
        st.stop()

creds = get_creds()
gc = gspread.authorize(creds)
drive_service = build('drive', 'v3', credentials=creds)

# Open Sheet (Ensure name is exactly "Study Mistake Log")
try:
    sh = gc.open("Study Mistake Log")
    worksheet = sh.worksheet("Mistakes")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.info("Check if your Google Sheet is shared with the service account email.")
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

    if st.button("🚀 Upload & Save"):
        if uploaded_file:
            with st.spinner("Uploading to Google Drive..."):
                try:
                    # 1. Upload to Google Drive
                    file_metadata = {
                        'name': f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}",
                        'parents': [DRIVE_FOLDER_ID]
                    }
                    media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), 
                                              mimetype=uploaded_file.type)
                    
                    uploaded_drive_file = drive_service.files().create(
                        body=file_metadata, media_body=media, fields='id, webViewLink'
                    ).execute()
                    
                    image_link = uploaded_drive_file.get('webViewLink')

                    # 2. Save to Google Sheet
                    new_row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        image_link, 
                        subject,
                        topic_tag.title(),
                        notes
                    ]
                    worksheet.append_row(new_row)
                    st.success("✅ Saved Permanently!")
                    st.balloons()
                except Exception as upload_error:
                    st.error(f"Upload failed: {upload_error}")
        else:
            st.error("Please upload an image first!")

# --- 🔍 DISPLAY DATA ---
st.subheader("Your Mistake Log")
try:
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        
        # Configure the link column to be clickable
        st.dataframe(
            df, 
            column_config={
                "Image": st.column_config.LinkColumn("View Question", display_text="Open Image 🔗")
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No mistakes logged yet.")
except Exception as read_error:
    st.error(f"Could not read data: {read_error}")
