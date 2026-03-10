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
st.title("📚 Exam Error Bank")

# --- SIDEBAR: LOGGING ---
with st.sidebar:
    st.header("📸 Log New Mistake")
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="New Upload Preview", use_container_width=True)
    
    subject = st.selectbox("Subject", ['Maths', 'Verbal Reasoning', 'Non-Verbal', 'English', 'SPAG'])
    topic_tag = st.text_input("Topic (e.g. Fractions)")
    notes = st.text_area("Notes")

    if st.button("🚀 Save Mistake"):
        if uploaded_file:
            with st.spinner("Saving..."):
                try:
                    img = Image.open(uploaded_file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    img.thumbnail((500, 500)) 
                    buffered = BytesIO()
                    img.save(buffered, format="JPEG", quality=50)
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    image_data = f"data:image/jpeg;base64,{img_str}"

                    # Updated Header Row for the first time if sheet is empty
                    if not worksheet.get_all_values():
                        worksheet.append_row(["Timestamp", "ImageData", "Subject", "Topic", "Notes"])

                    new_row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        image_data, 
                        subject,
                        topic_tag.title(),
                        notes
                    ]
                    worksheet.append_row(new_row)
                    st.success("✅ Saved!")
                    st.rerun()
                except Exception as err:
                    st.error(f"Error: {err}")
        else:
            st.error("Upload an image first!")

# --- 🔍 FILTER & DISPLAY ---
st.subheader("🔍 Review & Search")

try:
    data = worksheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        
        # --- 🛡️ COLUMN SAFETY CHECK ---
        # We find which column contains the long data string (ImageData)
        # This prevents the "not found in axis" error
        image_col = None
        for col in df.columns:
            if df[col].astype(str).str.contains('data:image', na=False).any():
                image_col = col
                break
        
        # 1. Filters
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            all_subjects = ["All"] + sorted(df['Subject'].unique().tolist())
            sel_sub = st.selectbox("Filter Subject:", all_subjects)
        with col_f2:
            search_txt = st.text_input("Search Topics/Notes:")

        # Apply Filters
        filtered_df = df.copy()
        if sel_sub != "All":
            filtered_df = filtered_df[filtered_df['Subject'] == sel_sub]
        if search_txt:
            # Flexible search across all text columns
            mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_txt, case=False)).any(axis=1)
            filtered_df = filtered_df[mask]

        # 2. Table Display
        st.write("### 1. Select a row to view or delete:")
        
        # Drop the image data column ONLY if we found it, so the table stays clean
        display_df = filtered_df.drop(columns=[image_col]) if image_col else filtered_df
        
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        # 3. Actions Section
        st.divider()
        
        if len(event.selection.rows) > 0:
            selected_row_index = event.selection.rows[0]
            selected_row_data = filtered_df.iloc[selected_row_index]
            
            view_col, del_col = st.columns([3, 1])
            
            with view_col:
                topic_display = selected_row_data.get('Topic', 'Selected Mistake')
                st.write(f"### 🖼️ Preview: {topic_display}")
                
                if image_col and str(selected_row_data[image_col]).startswith("data:image"):
                    st.image(selected_row_data[image_col], use_container_width=True)
                else:
                    st.warning("No image data found in this row.")
            
            with del_col:
                st.write("### 🗑️ Actions")
                if st.button("Delete This Entry", type="primary"):
                    all_values = worksheet.get_all_values()
                    # Match by timestamp (Column A / Index 0)
                    target_ts = str(selected_row_data.iloc[0]) 
                    
                    row_to_delete = -1
                    for idx, row in enumerate(all_values):
                        if row[0] == target_ts:
                            row_to_delete = idx + 1
                            break
                    
                    if row_to_delete > 0:
                        worksheet.delete_rows(row_to_delete)
                        st.success("Deleted!")
                        st.rerun()
                    else:
                        st.error("Row not found in Sheet.")
        else:
            st.info("👆 Click a row in the table above to see the image.")

    else:
        st.info("Your Google Sheet is empty. Upload your first mistake!")
except Exception as read_error:
    st.error(f"Error loading data: {read_error}")
    st.info("Try deleting the first row of your Google Sheet if it has incorrect headers.")
