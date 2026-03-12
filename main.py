import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

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

try:
    sh = gc.open("Study Mistake Log")
    worksheet = sh.worksheet("Mistakes")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

# --- 🎨 APP INTERFACE ---
st.set_page_config(page_title="11+ Mistake Tracker", layout="wide")
st.title("📚 Fast High-Res Mistake Bank")

with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    subject = st.selectbox("Subject", ['Maths', 'Verbal Reasoning', 'Non-Verbal', 'English', 'SPAG'])
    topic_tag = st.text_input("Topic")
    notes = st.text_area("Notes")

    if st.button("🚀 Save Mistake"):
        if uploaded_file:
            with st.spinner("Optimizing & Uploading..."):
                try:
                    # --- 🛠️ STEP 1: RESIZE LOCALLY BEFORE UPLOAD ---
                    img = Image.open(uploaded_file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # 1600px is the "Goldilocks" size for exam papers
                    img.thumbnail((1600, 1600)) 
                    
                    # Save to a memory buffer
                    buffer = BytesIO()
                    img.save(buffer, format="JPEG", quality=85) # 85 is great for text
                    optimized_image = buffer.getvalue()

                    # --- 🚀 STEP 2: UPLOAD SMALLER FILE ---
                    files = {"image": optimized_image}
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
                        st.success("✅ Saved Fast!")
                        st.rerun()
                    else:
                        st.error("Upload failed.")
                except Exception as err:
                    st.error(f"Error: {err}")
        else:
            st.error("Please upload an image!")

# --- 🔍 REVIEW & SEARCH ---
st.subheader("🔍 Review Mistakes")

try:
    data = worksheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
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

        # Table Display
        display_df = filtered_df.drop(columns=[img_col]) if img_col else filtered_df
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if len(event.selection.rows) > 0:
            row_idx = event.selection.rows[0]
            url = filtered_df.iloc[row_idx][img_col]
            
            st.divider()
            st.image(url, caption="High-Res Preview", use_container_width=True)
            st.markdown(f"[🔗 Open Full Size]({url})")
            
            if st.button("Delete Entry", type="primary"):
                all_vals = worksheet.get_all_values()
                ts = str(filtered_df.iloc[row_idx].iloc[0])
                for i, r in enumerate(all_vals):
                    if r[0] == ts:
                        worksheet.delete_rows(i + 1)
                        st.rerun()
    else:
        st.info("No mistakes yet.")
except Exception as e:
    st.error(f"Error: {e}")
