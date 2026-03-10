import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# --- 🛡️ SECURE GOOGLE AUTHENTICATION ---
def get_gspread_client():
    try:
        # 1. Access the secret dictionary from Streamlit settings
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # 2. REPAIR THE KEY: Standardize the PEM format to avoid "InvalidByte" errors
        raw_key = creds_dict["private_key"]
        header = "-----BEGIN PRIVATE KEY-----"
        footer = "-----END PRIVATE KEY-----"
        
        # Strip everything to get just the base64 characters
        clean_key = raw_key.replace(header, "").replace(footer, "").replace("\n", "").replace(" ", "").strip()
        
        # Reconstruct with exactly one newline after header and before footer
        # This is the "shape" the cryptography library requires
        fixed_key = f"{header}\n{clean_key}\n{footer}"
        creds_dict["private_key"] = fixed_key
        
        # 3. Authorize
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        st.info("Check your Streamlit Secrets formatting.")
        st.stop()

# Initialize connection
gc = get_gspread_client()

# IMPORTANT: Make sure this name matches your Google Sheet exactly!
try:
    sh = gc.open("Study Mistake Log")
    worksheet = sh.worksheet("Mistakes")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.info("Ensure the sheet is named 'Study Mistake Log' and shared with your service account email.")
    st.stop()

# --- 🎨 APP INTERFACE ---
st.set_page_config(page_title="11+ Mistake Tracker", layout="wide")

st.title("📚 Exam Error Bank (Cloud Sync)")
st.markdown("Your data is automatically saved to Google Sheets.")

# --- SIDEBAR: LOGGING NEW ERRORS ---
with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Question Image", type=["png", "jpg", "jpeg"])
    
    subject = st.selectbox("Subject", 
                          ['Maths', 'Verbal Reasoning', 'Non-Verbal', 'English', 'SPAG', 'Science'])
    
    topic_tag = st.text_input("Topic (e.g. Fractions, Ratios)")
    
    notes = st.text_area("Why did you get this wrong?", 
                        placeholder="e.g. Misread the question, forgot to simplify...")

    if st.button("Save to Google Sheets"):
        if uploaded_file:
            # Prepare data row
            # Note: Since cloud hosting doesn't store files, we log the text data.
            # You can view the image in the Streamlit 'Preview' before saving.
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = [
                timestamp, 
                "Image Uploaded", # Placeholder for file
                subject, 
                topic_tag.title(), 
                notes, 
                datetime.now().strftime("%Y-%m-%d")
            ]
            
            worksheet.append_row(new_row)
            st.success("✅ Saved Successfully!")
            st.balloons()
        else:
            st.error("Please upload an image first!")

# --- MAIN DISPLAY: VIEWING ERRORS ---
st.subheader("🔍 Review Your Mistakes")

# Load data from Google Sheets
data = worksheet.get_all_records()

if data:
    df = pd.DataFrame(data)
    
    # Filter by Subject
    all_subjects = df['Subject'].unique().tolist()
    selected_sub = st.multiselect("Filter by Subject:", options=all_subjects, default=all_subjects)
    
    # Search by Notes
    search_query = st.text_input("Search notes/topics:")

    # Apply Filters
    filtered_df = df[df['Subject'].isin(selected_sub)]
    if search_query:
        filtered_df = filtered_df[filtered_df['Notes'].str.contains(search_query, case=False) | 
                                  filtered_df['Tags'].str.contains(search_query, case=False)]

    # Display Table
    st.dataframe(filtered_df, use_container_width=True)
    
    # Simple Progress Chart
    st.divider()
    st.subheader("📈 Mistake Distribution")
    sub_counts = filtered_df['Subject'].value_factory() if hasattr(filtered_df['Subject'], 'value_factory') else filtered_df['Subject'].value_counts()
    st.bar_chart(sub_counts)

else:
    st.info("Your mistake log is currently empty. Start by adding one in the sidebar!")
