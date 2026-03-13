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

# --- 🎨 PROFESSIONAL STYLING ---
st.set_page_config(page_title="11+ Mastery Bank", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    section[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e0e0e0; }
    [data-testid="stMetricValue"] { color: #2c3e50; font-weight: 700; }
    .stButton>button { border-radius: 8px; transition: all 0.3s ease; }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "active_image" not in st.session_state: st.session_state.active_image = None
if "f_date" not in st.session_state: st.session_state.f_date = 9999
if "current_quiz_item" not in st.session_state: st.session_state.current_quiz_item = None

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.subheader("🎓 Personal AI Tutor")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.active_image = None
        st.rerun()
            
    if st.session_state.active_image:
        st.image(st.session_state.active_image, caption="Analysing this mistake...", use_container_width=True)
        if st.button("✕ Remove Context", type="secondary"):
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
tab1, tab2, tab3, tab4 = st.tabs(["➕ Log Mistake", "🔍 Review Bank", "🎲 Quiz Mode", "📊 Progress Tracker"])

# --- TAB 1: ADD (FIXED DYNAMIC LABELS) ---
with tab1:
    # Fetch data once per run to get fresh topics
    raw_data = worksheet.get_all_values()
    df_raw = pd.DataFrame(raw_data[1:], columns=raw_data[0]) if len(raw_data) > 1 else pd.DataFrame()

    with st.container():
        st.write("### Capture a New Mistake")
        up = st.file_uploader("Upload Photo of the Question", type=["png", "jpg", "jpeg"])
        
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                # Added key="sub_selector" to help Streamlit track changes
                sub = st.selectbox("Select Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'], key="sub_selector")
            
            with c2:
                # Filter topics based on the subject currently selected in 'sub'
                filtered_topics = []
                if not df_raw.empty:
                    # Filter matching rows and get unique topics
                    filtered_topics = sorted(list(set(df_raw[df_raw['Subject'] == sub]['Topic'].unique())))
                
                # The label now injects the current value of 'sub' directly
                topic_choice = st.selectbox(f"Suggested {sub} Topics", ["New Topic..."] + filtered_topics)
            
            # Use the subject name in the placeholder as well
            if topic_choice == "New Topic...":
                topic_final = st.text_input(f"Enter New {sub} Topic Name")
            else:
                topic_final = topic_choice

            notes = st.text_area("Learning Notes")
            
            if st.form_submit_button("🚀 Save Mistake", use_container_width=True) and up:
                if not topic_final:
                    st.error(f"Please provide a topic name for this {sub} mistake.")
                else:
                    with st.spinner("Logging..."):
                        r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
                        if r.status_code == 200:
                            url = r.json()["data"]["image"]["url"]
                            worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, topic_final.strip().title(), notes, "No"])
                            st.success(f"Mistake logged under {sub} > {topic_final.title()}!")
                            st.rerun()

# --- TAB 2: REVIEW ---
with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        st.write("### Filter & Search")
        fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 2])
        with fc1: 
            if st.button("📅 All", use_container_width=True): st.session_state.f_date = 9999
        with fc2: 
            if st.button("🗓️ 7 Days", use_container_width=True): st.session_state.f_date = 7
        with fc3: 
            if st.button("⏳ Pending", use_container_width=True): st.session_state.f_date = 0
        with fc4:
            search = st.text_input("🔍 Search Topic or Notes")

        f_sub = st.selectbox("Filter by Subject", ["All Subjects"] + sorted(list(df['Subject'].unique())))
        
        f_df = df.copy()
        if st.session_state.f_date == 0:
            f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        elif st.session_state.f_date < 9999:
            f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
        
        if f_sub != "All Subjects": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        st.divider()

        for _, row in f_df.sort_values('dt', ascending=False).iterrows():
            is_m = row['Mastered'].strip().upper() == "YES"
            with st.container(border=True):
                c_title, c_ask, c_mast, c_del = st.columns([2, 1, 1, 1])
                c_title.markdown(f"**{row['Subject']}** • {row['Topic']}")
                with c_title.popover("🖼️ Open Image"):
                    st.image(row['ImageURL'])
                    st.write(f"**Notes:** {row['Notes']}")
                if c_ask.button("💬 Chat", key=f"ask_{row['SheetRow']}", use_container_width=True):
                    st.session_state.active_image = row['ImageURL']
                    st.toast("Sent to AI Tutor!")
                if c_mast.button("✅ Done" if is_m else "⬜ Mastery", key=f"m_{row['SheetRow']}", use_container_width=True):
                    worksheet.update_cell(row['SheetRow'], 6, "Yes" if not is_m else "No")
                    st.rerun()
                with c_del.popover("🗑️"):
                    if st.button("Confirm Delete", key=f"del_{row['SheetRow']}", type="primary"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("Your bank is currently empty.")

# --- TAB 3: QUIZ ---
with tab3:
    st.write("### Quick Revision Challenge")
    if st.button("🎲 Draw Random Question", type="primary"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            p = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not p.empty:
                st.session_state.current_quiz_item = p.sample(1).iloc[0]
            else:
                st.success("Bank Mastered!")
    
    if st.session_state.current_quiz_item is not None:
        sel = st.session_state.current_quiz_item
        with st.container(border=True):
            st.image(sel['ImageURL'], width=600)
            st.subheader(f"{sel['Subject']} Challenge: {sel['Topic']}")
            if st.button("💡 Ask AI for a Hint", key="quiz_hint", use_container_width=True):
                st.session_state.active_image = sel['ImageURL']
                hint_p = f"I'm reviewing this {sel['Subject']} question on {sel['Topic']}. Can you provide a clever hint?"
                st.session_state.messages.append({"role": "user", "content": hint_p})
                with st.spinner("Consulting AI..."):
                    response = chat_with_ai(hint_p, image_url=sel['ImageURL'])
                    st.session_state.messages.append({"role": "assistant", "content": response})
                st.toast("Hint in Sidebar Chat!")
                st.rerun()

# --- TAB 4: PROGRESS ---
with tab4:
    st.write("### Your Mastery Dashboard")
    if len(data) > 1:
        df_p = pd.DataFrame(data[1:], columns=data[0])
        total = len(df_p); mastered = len(df_p[df_p['Mastered'].str.upper() == "YES"])
        perc = (mastered/total)*100 if total > 0 else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Logged", total); c2.metric("Mastered", mastered); c3.metric("Mastery Rate", f"{perc:.1f}%")
        st.progress(perc/100)
        st.write("#### Subject Breakdown")
        st.bar_chart(df_p['Subject'].value_counts())
