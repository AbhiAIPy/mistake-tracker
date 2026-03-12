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
    st.error("Secrets missing! Please ensure GROQ_API_KEY is in your Streamlit secrets.")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🤖 UPDATED FREE AI LOGIC (GROQ) ---
def chat_with_ai(prompt, uploaded_file=None):
    try:
        messages = []
        if uploaded_file:
            img_b64 = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    }
                ]
            })
            # Swapped to the current active vision model
            model = "llama-3.2-90b-vision-preview"
        else:
            messages.append({"role": "user", "content": prompt})
            # Swapped to the current active text model
            model = "llama-3.3-70b-specdec"

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    st.caption("UK Stable Mode (Groq Free)")
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    chat_file = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])
    
    if "messages" not in st.session_state: 
        st.session_state.messages = []
        
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
        
    if prompt := st.chat_input("Ask about your mistake..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = chat_with_ai(prompt, chat_file)
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
        notes = st.text_area("Your Notes")
        if st.form_submit_button("🚀 Save Mistake") and up:
            with st.spinner("Uploading..."):
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
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        st.caption("Quick Filters:")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📅 Last 7 Days"): st.session_state.f_date = 7
        with c2:
            if st.button("🗓️ Last 14 Days"): st.session_state.f_date = 14
        with c3:
            if st.button("⏳ Unmastered"): st.session_state.f_date = 0

        st.divider()
        cs1, cs2 = st.columns([2, 1])
        with cs1:
            search = st.text_input("🔍 Search Topic/Notes")
        with cs2:
            f_sub = st.selectbox("Subject Filter", ["All"] + sorted(list(df['Subject'].unique())))

        f_df = df.copy()
        if 'f_date' in st.session_state:
            if st.session_state.f_date > 0:
                f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
            else:
                f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        
        if f_sub != "All": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        for _, row in f_df.sort_values('dt', ascending=True).iterrows():
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                cols = st.columns([1, 1, 1])
                with cols[0]:
                    with st.popover("🖼️ View Photo"): st.image(row['ImageURL'])
                with cols[1]:
                    m = row['Mastered'].strip().upper() == "YES"
                    if st.button("✅ Mastered" if m else "⬜ Mark Done", key=f"m_{row['SheetRow']}"):
                        worksheet.update_cell(row['SheetRow'], 6, "Yes" if not m else "No")
                        st.rerun()
                with cols[2]:
                    if st.button("🗑️ Delete", key=f"d_{row['SheetRow']}"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("Log is empty.")

with tab3:
    if st.button("🎯 Get Random Challenge"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            p = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not p.empty:
                sel = p.sample(1).iloc[0]
                st.image(sel['ImageURL'])
                st.subheader(f"{sel['Subject']}: {sel['Topic']}")

with tab4:
    st.info("Ready for PDF export.")
