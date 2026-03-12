import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
from groq import Groq

# --- ⚙️ CONFIGURATION ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error("Secrets missing!")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 AI LOGIC (GROQ 2026 STABLE) ---
def chat_with_ai(prompt, image_url=None, uploaded_file=None):
    try:
        messages = []
        model = "meta-llama/llama-4-scout-17b-16e-instruct" if (uploaded_file or image_url) else "llama-3.3-70b-versatile"

        content = [{"type": "text", "text": prompt}]
        
        # Handle either a fresh upload or a "Drag/Click" from the review tab
        if uploaded_file:
            img_data = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}})
        elif image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        messages.append({"role": "user", "content": content})
        completion = client.chat.completions.create(model=model, messages=messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "active_image" not in st.session_state: st.session_state.active_image = None

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    
    # Show if an image was "sent" from the Review tab
    if st.session_state.active_image:
        st.info("📸 Analyzing image from Review tab...")
        st.image(st.session_state.active_image, caption="Current Context")
        if st.button("❌ Clear Context"):
            st.session_state.active_image = None
            st.rerun()

    chat_file = st.file_uploader("Or Upload New Photo", type=["png", "jpg", "jpeg"])
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
        
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            response = chat_with_ai(prompt, st.session_state.active_image, chat_file)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP TABS ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

with tab1:
    up = st.file_uploader("Upload Mistake Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Notes")
        if st.form_submit_button("🚀 Save Mistake") and up:
            r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
            if r.status_code == 200:
                url = r.json()["data"]["image"]["url"]
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, topic.title(), notes, "No"])
                st.success("Logged!")

with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        
        # Dashboard logic...
        for _, row in df.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                cols = st.columns([1, 1, 1, 1])
                with cols[0]:
                    with st.popover("🖼️ View"): st.image(row['ImageURL'])
                with cols[1]:
                    # NEW FEATURE: The "Pseudo Drag-and-Drop"
                    if st.button("💬 Ask AI", key=f"chat_{row['SheetRow']}"):
                        st.session_state.active_image = row['ImageURL']
                        st.success("Sent to Sidebar Chat! Check the left panel.")
                with cols[2]:
                    m = row['Mastered'].strip().upper() == "YES"
                    if st.button("✅" if m else "⬜", key=f"m_{row['SheetRow']}"):
                        worksheet.update_cell(row['SheetRow'], 6, "Yes" if not m else "No")
                        st.rerun()
                with cols[3]:
                    if st.button("🗑️", key=f"d_{row['SheetRow']}"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("Log is empty.")

# (Tab 3 and 4 logic continues as before...)
