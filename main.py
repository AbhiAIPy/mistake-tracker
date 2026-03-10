import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# --- GOOGLE AUTH ---
# This connects to your Google Sheet
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("Study Mistake Log").worksheet("Mistakes")

st.set_page_config(page_title="Permanent Mistake Log", layout="wide")
st.title("📚 Permanent Exam Error Bank")

# Sidebar for Logging
with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Question", type=["png", "jpg", "jpeg"])
    subject = st.selectbox("Subject", ['Maths', 'Verbal', 'Non Verbal', 'SPAG', 'Comp', 'English'])
    topic_tag = st.text_input("Topic Tag")
    notes = st.text_area("Notes")
    
    if st.button("Save Permanently"):
        if uploaded_file:
            # In a real cloud app, you'd upload the image to Google Drive here 
            # and get a URL. For now, we store the metadata in the Sheet.
            new_row = [
                str(datetime.now().timestamp()), # ID
                "Image_In_Drive",                # Placeholder for Drive URL
                subject, 
                topic_tag.title(), 
                notes, 
                datetime.now().strftime("%Y-%m-%d")
            ]
            sheet.append_row(new_row)
            st.success("Data synced to Google Sheets!")
        else:
            st.error("Please upload an image.")

# --- DISPLAY FROM GOOGLE SHEETS ---
st.subheader("📊 Your Synced Mistakes")
data = sheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    st.dataframe(df) # Shows your Google Sheet data inside the app
else:
    st.info("No data found in Google Sheets.")
