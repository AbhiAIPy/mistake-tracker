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
# Custom CSS for bigger buttons and mobile spacing
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
        # Streamlit does not have a "strict" back-camera-only toggle yet, 
        # but most mobile browsers default to the rear camera for camera_input.
        uploaded_file = st.camera_input("Snap a photo of the question")
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
                        
                        # Automatic Header Setup if sheet is empty
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
        raw_data = worksheet.get_all_records()
        if raw_data:
            df = pd.DataFrame(raw_data)
            
            # --- THE FIX: Flexible Column Finder ---
            # This looks for any column containing 'image' or 'url' (case insensitive)
            img_col = next((c for c in df.columns if 'url' in c.lower() or 'image' in c.lower()), None)
            mast_col = next((c for c in df.columns if 'master' in c.lower()), "Mastered")
            
            if not img_col:
                st.error("Sheet Error: Please name your Column B 'ImageURL'")
                st.stop()

            # Mobile Filters
            col_a, col_b = st.columns(2)
            with col_a:
                f_sub = st.selectbox("Filter Subject:", ["All"] + list(df['Subject'].unique()))
            with col_b:
                show_mastered = st.toggle("Show Mastered", value=False)

            if f_sub != "All":
                df = df[df['Subject'] == f_sub]
            if not show_mastered:
                df = df[df[mast_col].astype(str).str.upper() != "YES"]

            # Display newest first
            for index, row in df.iloc[::-1].iterrows():
                with st.container(border=True):
                    st.subheader(f"{row['Subject']}: {row.get('Topic', 'No Topic')}")
                    st.image(row[img_col], use_container_width=True)
                    if row.get('Notes'):
                        st.info(f"💡 {row['Notes']}")
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("✅ Mastered", key=f"win_{index}"):
                            # Finding the correct column index for 'Mastered'
                            col_idx = df.columns.get_loc(mast_col) + 1
                            worksheet.update_cell(index + 2, col_idx, "Yes")
                            st.rerun()
                    with b2:
                        if st.button("🗑️ Delete", key=f"del_{index}"):
                            worksheet.delete_rows(index + 2)
                            st.rerun()
        else:
            st.info("No data found.")
    except Exception as e:
        st.error(f"Display Error: {e}")

# --- TAB 3: QUIZ ---
with tab3:
    st.header("Quick Quiz")
    if st.button("🎯 Random Question"):
        data = worksheet.get_all_records()
        unsolved = [d for d in data if str(d.get('Mastered', '')).upper() != "YES"]
        if unsolved:
            pick = random.choice(unsolved)
            # Find image column in the pick dictionary
            img_key = next((k for k in pick.keys() if 'url' in k.lower() or 'image' in k.lower()), None)
            st.image(pick[img_key], use_container_width=True)
            st.write(f"**Topic:** {pick.get('Topic', 'Unknown')}")
            with st.expander("Reveal Notes"):
                st.write(pick.get('Notes', 'No notes.'))
        else:
            st.warning("No new questions left!")
