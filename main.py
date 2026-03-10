import streamlit as st
import sqlite3
import os
from datetime import datetime

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('mistake_log.db')
    c = conn.cursor()
    # Added 'tags' column to the table
    c.execute('''CREATE TABLE IF NOT EXISTS mistakes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  image_path TEXT, 
                  subject TEXT, 
                  tags TEXT, 
                  notes TEXT, 
                  date TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- APP UI ---
st.set_page_config(page_title="11+ Mistake Tracker", layout="wide", page_icon="📝")
st.title("🎯 Exam Revision: Mistake Log")

# Sidebar for Logging
with st.sidebar:
    st.header("📸 Log New Question")
    uploaded_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    subject = st.selectbox("Subject", [
        'Maths', 'Verbal', 'Non Verbal', 'SPAG', 'Comp', 'English'
    ])
    
    # NEW: Topic Tag Input
    topic_tag = st.text_input("Topic Tag (e.g., 'Fractions', 'Synonyms', 'Punctuation')")
    
    notes = st.text_area("Notes/Reminders")
    
    if st.button("Save to Log"):
        if uploaded_file is not None:
            if not os.path.exists("saved_images"):
                os.makedirs("saved_images")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = os.path.join("saved_images", f"{subject}_{timestamp}.png")
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            conn = sqlite3.connect('mistake_log.db')
            c = conn.cursor()
            c.execute("INSERT INTO mistakes (image_path, subject, tags, notes, date) VALUES (?, ?, ?, ?, ?)",
                      (file_path, subject, topic_tag.strip().title(), notes, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            conn.close()
            st.success(f"Added to {subject}!")
            st.rerun() # Refresh to show new entry
        else:
            st.error("Please upload a file!")

# --- SEARCH & FILTER ---
st.subheader("🔍 Filter Your Mistakes")

# Load Data
conn = sqlite3.connect('mistake_log.db')
import pandas as pd
df = pd.read_sql_query("SELECT * FROM mistakes ORDER BY id DESC", conn)
conn.close()

if not df.empty:
    # Multi-column layout for filters
    f1, f2, f3 = st.columns([1, 1, 2])
    
    with f1:
        selected_subjects = st.multiselect("Subjects", options=df["subject"].unique(), default=df["subject"].unique())
    
    with f2:
        # NEW: Filter by specific tags found in the database
        unique_tags = sorted([t for t in df["tags"].unique() if t])
        selected_tags = st.multiselect("Topics/Tags", options=unique_tags)
    
    with f3:
        search_text = st.text_input("Search through notes...")

    # Apply Logic
    filtered_df = df[df["subject"].isin(selected_subjects)]
    if selected_tags:
        filtered_df = filtered_df[filtered_df["tags"].isin(selected_tags)]
    if search_text:
        filtered_df = filtered_df[filtered_df['notes'].str.contains(search_text, case=False, na=False)]

    # --- DISPLAY ---
    st.divider()
    if filtered_df.empty:
        st.warning("No results found.")
    else:
        for index, row in filtered_df.iterrows():
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.image(row['image_path'], use_container_width=True)
                with c2:
                    st.markdown(f"### {row['subject']} - {row['tags'] if row['tags'] else 'No Tag'}")
                    st.caption(f"📅 {row['date']}")
                    st.write(f"**Notes:** {row['notes']}")
                    
                    # Bonus: Mastered/Delete Button
                    if st.button(f"Mark as Mastered (Delete) #{row['id']}", key=f"del_{row['id']}"):
                        conn = sqlite3.connect('mistake_log.db')
                        c = conn.cursor()
                        c.execute("DELETE FROM mistakes WHERE id=?", (row['id'],))
                        conn.commit()
                        conn.close()
                        # Physically remove the image file too
                        if os.path.exists(row['image_path']):
                            os.remove(row['image_path'])
                        st.rerun()
                st.divider()
else:
    st.info("Log is empty. Upload your first mistake in the sidebar!")