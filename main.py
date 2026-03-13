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
    st.error("Secrets missing! Check Streamlit secrets for GROQ_API_KEY and IMGBB_API_KEY.")
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
        # Current stable models in UK
        model = "meta-llama/llama-4-scout-17b-16e-instruct" if (uploaded_file or image_url) else "llama-3.3-70b-versatile"

        content = [{"type": "text", "text": prompt}]
        if uploaded_file:
            img_data = base64.b64encode(uploaded_file.getvalue()).decode('utf-8')
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}})
        elif image_url:
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        messages.append({"role": "user", "content": content})
        completion = client.chat.completions.create(model=model, messages=messages, temperature=0.6)
        return completion.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="wide")

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "active_image" not in st.session_state: st.session_state.active_image = None
if "f_date" not in st.session_state: st.session_state.f_date = 9999
if "current_quiz_item" not in st.session_state: st.session_state.current_quiz_item = None

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.session_state.active_image = None
        st.rerun()
            
    if st.session_state.active_image:
        st.info("📸 Context: Active Question")
        st.image(st.session_state.active_image, use_container_width=True)
        if st.button("❌ Remove Image Context"):
            st.session_state.active_image = None
            st.rerun()

    chat_file = st.file_uploader("Upload New Image", type=["png", "jpg", "jpeg"])
    
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
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add Mistake", "🔍 Review Bank", "🎲 Quiz", "📊 Progress"])

# --- TAB 1: ADD ---
with tab1:
    up = st.file_uploader("Upload Mistake Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic")
        notes = st.text_area("Your Notes")
        if st.form_submit_button("🚀 Save Mistake") and up:
            with st.spinner("Logging..."):
                r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
                if r.status_code == 200:
                    url = r.json()["data"]["image"]["url"]
                    worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, topic.title(), notes, "No"])
                    st.success("Mistake logged!")

# --- TAB 2: REVIEW ---
with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        st.subheader("Filter Your Bank")
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1: 
            if st.button("📅 All Time"): st.session_state.f_date = 9999
        with fc2: 
            if st.button("🗓️ Last 7 Days"): st.session_state.f_date = 7
        with fc3: 
            if st.button("⏳ Unmastered"): st.session_state.f_date = 0
        with fc4:
            search = st.text_input("🔍 Search Topic/Notes")

        f_sub = st.selectbox("Subject", ["All"] + sorted(list(df['Subject'].unique())))

        f_df = df.copy()
        if st.session_state.f_date == 0:
            f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        elif st.session_state.f_date < 9999:
            f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
        
        if f_sub != "All": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        for _, row in f_df.sort_values('dt', ascending=False).iterrows():
            with st.container(border=True):
                c_title, c_ask, c_mast, c_del = st.columns([2, 1, 1, 1])
                c_title.write(f"**{row['Subject']}**: {row['Topic']}")
                with c_title.popover("🖼️ View"):
                    st.image(row['ImageURL'])
                    st.caption(f"Notes: {row['Notes']}")

                if c_ask.button("💬 Ask AI", key=f"ask_{row['SheetRow']}"):
                    st.session_state.active_image = row['ImageURL']
                    st.toast("Question sent to AI Chat!")
                
                is_m = row['Mastered'].strip().upper() == "YES"
                if c_mast.button("✅ Mastered" if is_m else "⬜ Mark Done", key=f"m_{row['SheetRow']}"):
                    worksheet.update_cell(row['SheetRow'], 6, "Yes" if not is_m else "No")
                    st.rerun()

                with c_del.popover("🗑️ Delete"):
                    st.warning("Sure?")
                    if st.button("Confirm", key=f"del_{row['SheetRow']}", type="primary"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("Empty Bank.")

# --- TAB 3: QUIZ ---
with tab3:
    if st.button("🎯 Get Random Challenge"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            p = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not p.empty:
                st.session_state.current_quiz_item = p.sample(1).iloc[0]
            else:
                st.info("All mastered!")
        else:
            st.info("No data.")

    if st.session_state.current_quiz_item is not None:
        sel = st.session_state.current_quiz_item
        st.image(sel['ImageURL'], width=500)
        st.subheader(f"Topic: {sel['Topic']}")
        
        # FEATURE: Get Hint sends to sidebar
        if st.button("💡 Get Hint from AI", key="quiz_hint"):
            st.session_state.active_image = sel['ImageURL']
            hint_prompt = "I'm doing a quiz on this mistake. Can you give me a small hint?"
            st.session_state.messages.append({"role": "user", "content": hint_prompt})
            with st.spinner("AI thinking..."):
                response = chat_with_ai(hint_prompt, image_url=sel['ImageURL'])
                st.session_state.messages.append({"role": "assistant", "content": response})
            st.toast("Hint sent to Chat!")
            st.rerun()

# --- TAB 4: PROGRESS ---
with tab4:
    st.subheader("Mastery Progress")
    if len(data) > 1:
        df_p = pd.DataFrame(data[1:], columns=data[0])
        total = len(df_p)
        mastered = len(df_p[df_p['Mastered'].str.upper() == "YES"])
        perc = (mastered/total)*100 if total > 0 else 0
        st.metric("Overall Mastery", f"{perc:.1f}%")
        st.progress(perc/100)
