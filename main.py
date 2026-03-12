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

try:
    sh = gc.open("Study Mistake Log")
    worksheet = sh.worksheet("Mistakes")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

# --- 🎨 APP INTERFACE ---
st.set_page_config(page_title="11+ Mistake Tracker", layout="wide")
st.title("📚 Exam Error Bank (Max Quality)")

with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="New Upload Preview", use_container_width=True)
    
    subject = st.selectbox("Subject", ['Maths', 'Verbal Reasoning', 'Non-Verbal', 'English', 'SPAG'])
    topic_tag = st.text_input("Topic")
    notes = st.text_area("Notes")

    if st.button("🚀 Save Mistake"):
        if uploaded_file:
            with st.spinner("Optimizing for Maximum Quality..."):
                try:
                    img = Image.open(uploaded_file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # --- SMART COMPRESSION LOOP ---
                    # We start with a large resolution and high quality
                    img.thumbnail((1000, 1000)) 
                    quality = 95
                    image_data = ""
                    
                    # Keep lowering quality until the string is < 50,000 characters
                    for q in range(95, 10, -5):
                        buffered = BytesIO()
                        img.save(buffered, format="JPEG", quality=q)
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        temp_data = f"data:image/jpeg;base64,{img_str}"
                        
                        if len(temp_data) <= 49500: # Safety margin
                            image_data = temp_data
                            quality_used = q
                            break
                    
                    if not image_data:
                        st.error("Image is too complex to fit even at low quality. Try a simpler screenshot.")
                    else:
                        if not worksheet.get_all_values():
                            worksheet.append_row(["Timestamp", "ImageData", "Subject", "Topic", "Notes"])

                        new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), image_data, subject, topic_tag.title(), notes]
                        worksheet.append_row(new_row)
                        st.success(f"✅ Saved at {quality_used}% quality!")
                        st.rerun()
                except Exception as err:
                    st.error(f"Error: {err}")
        else:
            st.error("Upload an image first!")

# --- 🔍 FILTER & DISPLAY ---
st.subheader("🔍 Review & Search")

try:
    raw_data = worksheet.get_all_records()
    if raw_data:
        df = pd.DataFrame(raw_data)
        
        sub_col = next((c for c in df.columns if c.lower() == 'subject'), None)
        topic_col = next((c for c in df.columns if c.lower() == 'topic'), None)
        img_col = next((c for c in df.columns if 'image' in c.lower()), None)

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_subjects = ["All"] + sorted(df[sub_col].unique().tolist())
            sel_sub = st.selectbox("Filter Subject:", all_subjects)
        with col_f2:
            search_txt = st.text_input("Search Topics/Notes:")

        filtered_df = df.copy()
        if sel_sub != "All":
            filtered_df = filtered_df[filtered_df[sub_col] == sel_sub]
        if search_txt:
            mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_txt, case=False)).any(axis=1)
            filtered_df = filtered_df[mask]

        st.write("### 1. Select a row to view:")
        cols_to_show = [c for c in filtered_df.columns if c != img_col]
        
        event = st.dataframe(
            filtered_df[cols_to_show], 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        st.divider()
        if len(event.selection.rows) > 0:
            selected_row_index = event.selection.rows[0]
            selected_row_data = filtered_df.iloc[selected_row_index]
            
            view_col, del_col = st.columns([3, 1])
            with view_col:
                st.write(f"### 🖼️ Preview")
                if img_col and str(selected_row_data[img_col]).startswith("data:image"):
                    st.image(selected_row_data[img_col], use_container_width=True)
            
            with del_col:
                if st.button("Delete This Entry", type="primary"):
                    all_values = worksheet.get_all_values()
                    target_ts = str(selected_row_data.iloc[0]) 
                    for idx, row in enumerate(all_values):
                        if row[0] == target_ts:
                            worksheet.delete_rows(idx + 1)
                            st.rerun()
        else:
            st.info("👆 Click a row to see the image.")
    else:
        st.info("Sheet is empty.")
except Exception as read_error:
    st.error(f"Display Error: {read_error}")
