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

# --- 🤖 AI LOGIC ---
def chat_with_ai(prompt, image_url=None, uploaded_file=None):
    try:
        messages = []
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

# --- 🎨 STAND-OUT INTERACTIVE STYLING ---
st.set_page_config(page_title="11+ Mastery Bank", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    
    /* Headings */
    h1, h2, h3 { color: #1e3a8a !important; font-weight: 800 !important; }
    
    /* Interactive Button Styling */
    .stButton>button {
        border-radius: 12px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
        padding: 10px 20px !important;
        transition: all 0.3s ease !important;
        border: 2px solid transparent !important;
    }

    /* Primary Buttons (Ask AI / Save) */
    div[data-testid="stFormSubmitButton"] button, 
    button[kind="primary"] {
        background-color: #2563eb !important;
        color: white !important;
        box-shadow: 0 4px 14px 0 rgba(37, 99, 235, 0.39) !important;
    }
    
    /* Mastery / Done Buttons (Success Green) */
    button:contains("MARK DONE"), button:contains("MASTERED"), button:contains("DONE") {
        background-color: #10b981 !important;
        color: white !important;
        box-shadow: 0 4px 14px 0 rgba(16, 185, 129, 0.39) !important;
    }

    /* Hover effects */
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
        border-color: rgba(255,255,255,0.5) !important;
    }

    /* Tab Label Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #f1f5f9;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 700;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e3a8a !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "active_image" not in st.session_state: st.session_state.active_image = None
if "f_date" not in st.session_state: st.session_state.f_date = 9999
if "current_quiz_item" not in st.session_state: st.session_state.current_quiz_item = None

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.markdown("## 🎓 AI TUTOR")
    if st.button("🗑️ CLEAR CHAT", use_container_width=True):
        st.session_state.messages = []
        st.session_state.active_image = None
        st.rerun()
    if st.session_state.active_image:
        st.image(st.session_state.active_image, use_container_width=True, caption="Current Context")
    chat_file = st.file_uploader("UPLOAD NEW IMAGE", type=["png", "jpg", "jpeg"])
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            response = chat_with_ai(prompt, st.session_state.active_image, chat_file)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN TABS ---
st.markdown("# 🧠 11+ MASTERY BANK")
tab1, tab2, tab3, tab4 = st.tabs(["➕ LOG MISTAKE", "🔍 REVIEW BANK", "🎲 QUIZ MODE", "📊 PROGRESS"])

# --- TAB 1: ADD ---
with tab1:
    raw_data = worksheet.get_all_values()
    df_raw = pd.DataFrame(raw_data[1:], columns=raw_data[0]) if len(raw_data) > 1 else pd.DataFrame()
    st.markdown("### 📝 RECORD NEW CHALLENGE")
    selected_sub = st.selectbox("1. SELECT SUBJECT", ['Maths', 'VR', 'NVR', 'English', 'SPAG'], key="main_sub")
    filtered_topics = []
    if not df_raw.empty:
        filtered_topics = sorted(list(set(df_raw[df_raw['Subject'] == selected_sub]['Topic'].unique())))

    with st.form("add_form", clear_on_submit=True):
        up = st.file_uploader("2. UPLOAD QUESTION PHOTO", type=["png", "jpg", "jpeg"])
        topic_choice = st.selectbox(f"3. SUGGESTED {selected_sub.upper()} TOPICS", ["New Topic..."] + filtered_topics, key=f"topic_{selected_sub}")
        if topic_choice == "New Topic...":
            topic_final = st.text_input(f"4. ENTER NEW {selected_sub.upper()} TOPIC", key=f"new_t_{selected_sub}")
        else:
            topic_final = topic_choice
        notes = st.text_area("5. LEARNING NOTES")
        if st.form_submit_button("🚀 SAVE TO BANK", use_container_width=True) and up:
            if not topic_final:
                st.error("Topic required.")
            else:
                with st.spinner("Logging..."):
                    r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
                    if r.status_code == 200:
                        url = r.json()["data"]["image"]["url"]
                        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, selected_sub, topic_final.strip().title(), notes, "No"])
                        st.success(f"Logged: {topic_final.title()}")
                        st.rerun()

# --- TAB 2: REVIEW ---
with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        st.markdown("### 🔍 SEARCH & FILTER")
        fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 2])
        with fc1: 
            if st.button("📅 ALL TIME", use_container_width=True, key="btn_all"): st.session_state.f_date = 9999
        with fc2: 
            if st.button("🗓️ 7 DAYS", use_container_width=True, key="btn_7"): st.session_state.f_date = 7
        with fc3: 
            if st.button("⏳ PENDING", use_container_width=True, key="btn_0"): st.session_state.f_date = 0
        with fc4:
            search = st.text_input("SEARCH...", label_visibility="collapsed", placeholder="Search topics...", key="search_in")

        f_sub = st.selectbox("FILTER BY SUBJECT", ["All Subjects"] + sorted(list(df['Subject'].unique())))
        f_df = df.copy()
        if st.session_state.f_date == 0:
            f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        elif st.session_state.f_date < 9999:
            f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
        if f_sub != "All Subjects": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        for _, row in f_df.sort_values('dt', ascending=False).iterrows():
            with st.container(border=True):
                c_title, c_ask, c_mast, c_del = st.columns([2, 1, 1, 1])
                c_title.markdown(f"#### {row['Subject']} : {row['Topic']}")
                with c_title.popover("🖼️ VIEW QUESTION"):
                    st.image(row['ImageURL'])
                    st.info(f"Notes: {row['Notes']}")
                
                # Interactive buttons
                if c_ask.button("💬 ASK AI", key=f"ask_{row['SheetRow']}", use_container_width=True, kind="primary"):
                    st.session_state.active_image = row['ImageURL']
                    st.toast("Context sent to AI Tutor!")
                
                is_m = row['Mastered'].strip().upper() == "YES"
                if c_mast.button("✅ DONE" if is_m else "⬜ MARK DONE", key=f"m_{row['SheetRow']}", use_container_width=True):
                    worksheet.update_cell(row['SheetRow'], 6, "Yes" if not is_m else "No")
                    st.rerun()

                with c_del.popover("🗑️ DELETE"):
                    if st.button("CONFIRM DELETE", key=f"del_{row['SheetRow']}", type="primary", use_container_width=True):
                        worksheet.delete_rows(row['SheetRow']); st.rerun()
    else: st.info("Bank is empty.")

# --- TAB 3: QUIZ ---
with tab3:
    st.markdown("### 🎲 QUICK CHALLENGE")
    if st.button("DRAW RANDOM QUESTION", type="primary", use_container_width=True):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            p = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not p.empty: st.session_state.current_quiz_item = p.sample(1).iloc[0]
            else: st.success("Everything mastered!")
    if st.session_state.current_quiz_item is not None:
        sel = st.session_state.current_quiz_item
        with st.container(border=True):
            st.image(sel['ImageURL'], width=600)
            st.markdown(f"## {sel['Subject']}: {sel['Topic']}")
            if st.button("💡 GET AI HINT", key="quiz_hint", use_container_width=True, kind="primary"):
                st.session_state.active_image = sel['ImageURL']
                hint_p = f"Give me a hint for this {sel['Subject']} question."
                st.session_state.messages.append({"role": "user", "content": hint_p})
                with st.spinner("Asking AI..."):
                    response = chat_with_ai(hint_p, image_url=sel['ImageURL'])
                    st.session_state.messages.append({"role": "assistant", "content": response})
                st.toast("Hint available in Sidebar Chat!"); st.rerun()

# --- TAB 4: PROGRESS ---
with tab4:
    st.markdown("### 📊 MASTERY DASHBOARD")
    if len(data) > 1:
        df_p = pd.DataFrame(data[1:], columns=data[0])
        total = len(df_p); mastered = len(df_p[df_p['Mastered'].str.upper() == "YES"])
        perc = (mastered/total)*100 if total > 0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL LOGS", total); c2.metric("MASTERED", mastered); c3.metric("SUCCESS RATE", f"{perc:.1f}%")
        st.progress(perc/100)
        st.bar_chart(df_p['Subject'].value_counts())
