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
    # Get all data and store in session state for easier deletion handling
    data = worksheet.get_all_records()
    
    if data:
        df = pd.DataFrame(data)
        
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
            filtered_df = filtered_df[
                filtered_df['Topic'].astype(str).str.contains(search_txt, case=False) | 
                filtered_df['Notes'].astype(str).str.contains(search_txt, case=False)
            ]

        # 2. Table Display
        st.write("### 1. Select a row to view or delete:")
        # We drop 'Image' for the table display to keep it clean
        display_df = filtered_df.drop(columns=['Image'])
        
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=False, # Show index so we can identify the row
            on_select="rerun",
            selection_mode="single-row"
        )

        # 3. Actions Section (Preview & Delete)
        st.divider()
        
        if len(event.selection.rows) > 0:
            # Get the actual index from the filtered dataframe
            selected_row_index = event.selection.rows[0]
            selected_row_data = filtered_df.iloc[selected_row_index]
            
            # Create two columns for View and Delete
            view_col, del_col = st.columns([3, 1])
            
            with view_col:
                st.write(f"### 🖼️ Preview: {selected_row_data['Topic']}")
                img_uri = selected_row_data['Image']
                if img_uri.startswith("data:image"):
                    st.image(img_uri, use_container_width=True)
            
            with del_col:
                st.write("### 🗑️ Actions")
                if st.button("Delete This Entry", type="primary"):
                    # Finding the row number in Google Sheets
                    # +2 because: 1 for header row, 1 because Dataframe is 0-indexed
                    # We match based on the unique Timestamp to be safe
                    all_values = worksheet.get_all_values()
                    target_timestamp = selected_row_data['Timestamp']
                    
                    row_to_delete = -1
                    for idx, row in enumerate(all_values):
                        if row[0] == target_timestamp:
                            row_to_delete = idx + 1
                            break
                    
                    if row_to_delete > 0:
                        worksheet.delete_rows(row_to_delete)
                        st.success("Entry deleted!")
                        st.rerun()
                    else:
                        st.error("Could not find row to delete.")
        else:
            st.info("👆 Click a row in the table above to see the image and delete options.")

    else:
        st.info("No mistakes logged yet.")
except Exception as read_error:
    st.error(f"Error loading data: {read_error}")
