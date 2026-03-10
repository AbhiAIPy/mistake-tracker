import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# --- SECURE AUTHENTICATION ---
try:
    # This looks for the [gcp_service_account] section in your Secrets
    if "gcp_service_account" not in st.secrets:
        st.error("Secret 'gcp_service_account' not found in Streamlit Settings!")
        st.stop()

    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
    client = gspread.authorize(creds)
    
    # Open your sheet (Make sure the name matches exactly!)
    sheet = client.open("Study Mistake Log").worksheet("Mistakes")
except Exception as e:
    st.error(f"Authentication Error: {e}")
    st.info("Check if you shared your Google Sheet with the client_email found in your secrets.")
    st.stop()

# --- APP INTERFACE ---
st.set_page_config(page_title="11+ Mistake Log", layout="wide")
st.title("📚 Exam Mistake Cloud Log")

with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Question", type=["png", "jpg", "jpeg"])
    subject = st.selectbox("Subject", ['Maths', 'Verbal', 'Non Verbal', 'SPAG', 'Comp', 'English'])
    topic_tag = st.text_input("Topic Tag (e.g., Fractions)")
    notes = st.text_area("Notes (Why was it wrong?)")
    
    if st.button("Save to Cloud"):
        if uploaded_file:
            # Metadata to save to Google Sheets
            new_row = [
                datetime.now().strftime("%Y%m%d%H%M%S"), 
                "Image_Logged", 
                subject, 
                topic_tag.title(), 
                notes, 
                datetime.now().strftime("%Y-%m-%d")
            ]
            sheet.append_row(new_row)
            st.success("✅ Logged successfully!")
            st.rerun()
        else:
            st.error("Please upload an image.")

# --- DISPLAY LOG ---
st.subheader("📊 Your Revision List")
data = sheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    
    # Filter controls
    col1, col2 = st.columns(2)
    with col1:
        chosen_sub = st.multiselect("Filter Subject", options=df['Subject'].unique(), default=df['Subject'].unique())
    with col2:
        search = st.text_input("Search Notes")
    
    filtered_df = df[df['Subject'].isin(chosen_sub)]
    if search:
        filtered_df = filtered_df[filtered_df['Notes'].str.contains(search, case=False)]
        
    st.table(filtered_df)
else:
    st.write("No mistakes logged yet.")
