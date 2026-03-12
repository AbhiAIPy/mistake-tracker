import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
import requests

# --- ⚙️ CONFIGURATION ---
IMGBB_API_KEY = "2eb6ef412c6d18c5c08e7f0f7232c042"

# --- 🛡️ SECURE AUTHENTICATION ---
def get_creds():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        raw_key = creds_dict["private_key"]
        header, footer = "-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----"
        clean_key = raw_key.replace(header, "").replace(footer, "").replace("\n", "").replace(" ", "").strip()
        creds_dict["private_key"] = f"{header}\n{clean_key}\n{footer}"
        
        # --- THE FIX IS HERE: ADDED BOTH DRIVE AND SPREADSHEETS SCOPES ---
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        return Credentials.from_service_account_info(creds_dict, scopes=scope)
    except Exception as e:
        st.error(f"Secret Error: {e}")
        st.stop()

creds = get_creds()
gc = gspread.authorize(creds)

# Open Sheet
try:
    # Ensure this matches your Google Sheet name exactly
    sh = gc.open("Study Mistake Log")
    worksheet = sh.worksheet("Mistakes")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.info("Check if you shared the sheet with the service account email as an 'Editor'.")
    st.stop()

# --- 🎨 APP INTERFACE ---
st.set_page_config(page_title="11+ Mistake Tracker", layout="wide")
st.title("📚 Original Quality Error Bank")

# --- SIDEBAR: LOGGING ---
with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Original Image", type=["png", "jpg", "jpeg"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="Selected Image", use_container_width=True)
    
    subject = st.selectbox("Subject", ['Maths', 'Verbal Reasoning', 'Non-Verbal', 'English', 'SPAG'])
    topic_tag = st.text_input("Topic")
    notes = st.text_area("Notes")

    if st.button("🚀 Save Mistake"):
        if uploaded_file:
            with st.spinner("Uploading to Cloud..."):
                try:
                    files = {"image": uploaded_file.getvalue()}
                    payload = {"key": IMGBB_API_KEY}
                    response = requests.post("https://api.imgbb.com/1/upload", data=payload, files=files)
                    
                    if response.status_code == 200:
                        image_url = response.json()["data"]["url"]

                        if not worksheet.get_all_values():
                            worksheet.append_row(["Timestamp", "ImageURL", "Subject", "Topic", "Notes"])

                        new_row = [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            image_url, 
                            subject,
                            topic_tag.title(),
                            notes
                        ]
                        worksheet.append_row(new_row)
                        st.success("✅ Saved at Original Quality!")
                        st.rerun()
                    else:
                        st.error(f"ImgBB Error: {response.text}")
                except Exception as err:
                    st.error(f"Upload Error: {err}")
        else:
            st.error("Please upload an image first!")

# --- 🔍 REVIEW & SEARCH ---
st.subheader("🔍 Review Mistakes")

try:
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        
        # Flexibly find the image column
        img_col = next((c for c in df.columns if 'url' in c.lower() or 'image' in c.lower()), None)
        sub_col = next((c for c in df.columns if 'subject' in c.lower()), "Subject")

        c1, c2 = st.columns(2)
        with c1:
            sel_sub = st.selectbox("Filter Subject:", ["All"] + sorted(df[sub_col].unique().tolist()))
        with c2:
            search = st.text_input("Search Topics/Notes:")

        filtered_df = df.copy()
        if sel_sub != "All":
            filtered_df = filtered_df[filtered_df[sub_col] == sel_sub]
        if search:
            mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
            filtered_df = filtered_df[mask]

        st.write("### 1. Select a mistake to view details:")
        # Hide the messy URL column from the table
        cols_to_display = [c for c in filtered_df.columns if c != img_col]
        
        event = st.dataframe(
            filtered_df[cols_to_display], 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if len(event.selection.rows) > 0:
            row_idx = event.selection.rows[0]
            url = filtered_df.iloc[row_idx][img_col]
            
            st.divider()
            col_img, col_act = st.columns([3, 1])
            
            with col_img:
                st.write(f"### 🖼️ Original Quality Preview")
                st.image(url, use_container_width=True)
                st.markdown(f"[🔗 Open in full size]({url})")
            
            with col_act:
                st.write("### 🗑️ Actions")
                if st.button("Delete Entry", type="primary"):
                    all_vals = worksheet.get_all_values()
                    ts = str(filtered_df.iloc[row_idx].iloc[0])
                    for i, r in enumerate(all_vals):
                        if r[0] == ts:
                            worksheet.delete_rows(i + 1)
                            st.rerun()
    else:
        st.info("Log your first high-res mistake!")
except Exception as e:
    st.error(f"Display Error: {e}")
