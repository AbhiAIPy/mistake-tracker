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
        # MARCH 2026 STABLE MODELS
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
if "f_date" not in st.session_state: st.session_state.f_date = 9999 # Default to all

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.title("🤖 AI Tutor Chat")
    
    col_chat1, col_chat2 = st.columns(2)
    with col_chat1:
        # Clear Chat with confirmation
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.session_state.active_image = None
            st.rerun()
            
    if st.session_state.active_image:
        st.info("📸 Analyzing image from Bank...")
        st.image(st.session_state.active_image, use_container_width=True)
        if st.button("❌ Remove Image"):
            st.session_state.active_image = None
            st.rerun()

    chat_file = st.file_uploader("Upload New Image", type=["png", "jpg", "jpeg"])
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
        
    if prompt := st.chat_input("Ask about your mistake..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            response = chat_with_ai(prompt, st.session_state.active_image, chat_file)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# --- 📊 MAIN APP TABS ---
st.title("🧠 11+ Mistake Bank")
tab1, tab2, tab3, tab4 = st.tabs(["➕ Add Mistake", "🔍 Review Bank", "🎲 Quiz", "📊 Progress"])

# --- TAB 1: ADD ---
with tab1:
    up = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        topic = st.text_input("Topic (e.g. Ratios, Synonyms)")
        notes = st.text_area("Why did you get it wrong?")
        if st.form_submit_button("🚀 Save to Bank") and up:
            with st.spinner("Uploading..."):
                r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
                if r.status_code == 200:
                    url = r.json()["data"]["image"]["url"]
                    worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, topic.title(), notes, "No"])
                    st.success("Added! Check the Review tab.")

# --- TAB 2: REVIEW (RESTORED FEATURES) ---
with tab2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['SheetRow'] = range(2, len(df) + 2)
        df['dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        # Dashboard Filters
        st.subheader("Filter Your Mistakes")
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1: 
            if st.button("📅 All Time"): st.session_state.f_date = 9999
        with fc2: 
            if st.button("🗓️ Last 7 Days"): st.session_state.f_date = 7
        with fc3: 
            if st.button("⏳ Unmastered"): st.session_state.f_date = 0
        with fc4:
            search = st.text_input("🔍 Search Topic/Notes")

        f_sub = st.selectbox("Subject Filter", ["All"] + sorted(list(df['Subject'].unique())))

        # Apply Filters
        f_df = df.copy()
        if st.session_state.f_date == 0:
            f_df = f_df[f_df['Mastered'].str.upper() != "YES"]
        elif st.session_state.f_date < 9999:
            f_df = f_df[f_df['dt'] > (datetime.now() - timedelta(days=st.session_state.f_date))]
        
        if f_sub != "All": f_df = f_df[f_df['Subject'] == f_sub]
        if search: f_df = f_df[f_df['Topic'].str.contains(search, case=False) | f_df['Notes'].str.contains(search, case=False)]

        st.divider()

        # Display Mistakes
        for _, row in f_df.sort_values('dt', ascending=False).iterrows():
            with st.container(border=True):
                c_title, c_ask, c_mast, c_del = st.columns([2, 1, 1, 1])
                
                c_title.write(f"**{row['Subject']}**: {row['Topic']}")
                
                # Popover to see image without leaving page
                with c_title.popover("🖼️ View Question"):
                    st.image(row['ImageURL'])
                    st.info(f"Notes: {row['Notes']}")

                # "Drag-and-Drop" Alternative: Send to AI
                if c_ask.button("💬 Ask AI", key=f"ask_{row['SheetRow']}"):
                    st.session_state.active_image = row['ImageURL']
                    st.toast("Question sent to AI Chat!")
                
                # Mastery Toggle
                is_m = row['Mastered'].strip().upper() == "YES"
                if c_mast.button("✅ Mastered" if is_m else "⬜ Mark Done", key=f"m_{row['SheetRow']}"):
                    worksheet.update_cell(row['SheetRow'], 6, "Yes" if not is_m else "No")
                    st.rerun()

                # Delete with confirmation
                with c_del.popover("🗑️ Delete"):
                    st.warning("Are you sure?")
                    if st.button("Confirm Delete", key=f"del_conf_{row['SheetRow']}", type="primary"):
                        worksheet.delete_rows(row['SheetRow'])
                        st.rerun()
    else:
        st.info("Log is currently empty.")

# --- TAB 3: QUIZ ---
with tab3:
    if st.button("🎯 Get Random Challenge"):
        all_d = worksheet.get_all_values()
        if len(all_d) > 1:
            df_q = pd.DataFrame(all_d[1:], columns=all_d[0])
            p = df_q[df_q['Mastered'].str.upper() != "YES"]
            if not p.empty:
                sel = p.sample(1).iloc[0]
                st.image(sel['ImageURL'], caption=f"{sel['Subject']} challenge")
                st.subheader(f"Topic: {sel['Topic']}")
                if st.button("Get Hint from AI"):
                    st.write(chat_with_ai("Give me a small hint for this question without giving the answer.", sel['ImageURL']))

# --- TAB 4: PROGRESS ---
with tab4:
    st.subheader("Revision Statistics")
    if len(data) > 1:
        df_p = pd.DataFrame(data[1:], columns=data[0])
        total = len(df_p)
        mastered = len(df_p[df_p['Mastered'].str.upper() == "YES"])
        perc = (mastered/total)*100 if total > 0 else 0
        st.metric("Mastery Score", f"{perc:.1f}%", f"{mastered} of {total} items")
        st.progress(perc/100)
    else:
        st.write("No data to show yet.")
