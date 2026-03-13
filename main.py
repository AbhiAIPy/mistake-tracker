import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
import io
import random
from PIL import Image
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

# --- 🖼️ IMAGE STITCHING LOGIC ---
def stitch_images(uploaded_files):
    if not uploaded_files: return None
    images = [Image.open(x).convert("RGB") for x in uploaded_files]
    min_width = images[0].size[0]
    resized_images = []
    for img in images:
        w_percent = (min_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        resized_images.append(img.resize((min_width, h_size), Image.Resampling.LANCZOS))
    
    total_height = sum(img.size[1] for img in resized_images)
    new_img = Image.new('RGB', (min_width, total_height))
    
    y_offset = 0
    for img in resized_images:
        new_img.paste(img, (0, y_offset))
        y_offset += img.size[1]
    
    img_byte_arr = io.BytesIO()
    new_img.save(img_byte_arr, format='JPEG', quality=85)
    return img_byte_arr.getvalue()

# --- 🎨 HIGH-IMPACT STYLING ---
st.set_page_config(page_title="11+ Mastery Bank", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    h1, h2, h3 { color: #1e3a8a !important; font-weight: 800 !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 700 !important; text-transform: uppercase !important; transition: all 0.3s ease !important; }
    button:contains("ASK AI"), button:contains("SAVE"), button:contains("HINT") { background-color: #2563eb !important; color: white !important; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2) !important; }
    button:contains("DONE"), button:contains("MASTERED") { background-color: #10b981 !important; color: white !important; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2) !important; }
    .stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 6px 15px rgba(0,0,0,0.1) !important; }
    
    /* Style for the "Open in New Tab" Link */
    .open-link {
        display: inline-block;
        margin-top: 10px;
        padding: 5px 15px;
        background-color: #f1f5f9;
        color: #1e3a8a;
        text-decoration: none;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.8rem;
        border: 1px solid #cbd5e1;
    }
    .open-link:hover { background-color: #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

# Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "active_image" not in st.session_state: st.session_state.active_image = None
if "f_date" not in st.session_state: st.session_state.f_date = 9999
if "current_quiz_item" not in st.session_state: st.session_state.current_quiz_item = None
if "upload_reset_counter" not in st.session_state: st.session_state.upload_reset_counter = 0

# --- 📟 SIDEBAR CHAT ---
with st.sidebar:
    st.markdown("## 🎓 AI TUTOR")
    if st.button("🗑️ CLEAR CHAT", use_container_width=True):
        st.session_state.messages = []
        st.session_state.active_image = None
        st.rerun()
    if st.session_state.active_image:
        st.image(st.session_state.active_image, use_container_width=True)
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

    uploader_key = f"uploader_{st.session_state.upload_reset_counter}"
    ups = st.file_uploader("2. UPLOAD PHOTO(S)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=uploader_key)
    
    processed_image = None
    if ups:
        with st.expander("👀 PREVIEW STITCHED IMAGE", expanded=True):
            processed_image = stitch_images(ups) if len(ups) > 1 else ups[0].getvalue()
            st.image(processed_image, caption=f"Combined View ({len(ups)} Files)", use_container_width=True)

    with st.form("add_form", clear_on_submit=True):
        topic_choice = st.selectbox(f"3. SUGGESTED {selected_sub.upper()} TOPICS", ["New Topic..."] + filtered_topics, key=f"topic_{selected_sub}")
        if topic_choice == "New Topic...":
            topic_final = st.text_input(f"4. ENTER NEW {selected_sub.upper()} TOPIC", key=f"new_t_{selected_sub}")
        else:
            topic_final = topic_choice
        notes = st.text_area("5. LEARNING NOTES")
        
        if st.form_submit_button("🚀 SAVE TO BANK", use_container_width=True):
            if not ups:
                st.error("Please upload at least one image.")
            elif not topic_final:
                st.error("Topic required.")
            else:
                with st.spinner("Processing..."):
                    final_bytes = stitch_images(ups) if len(ups) > 1 else ups[0].getvalue()
                    r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": final_bytes})
                    if r.status_code == 200:
                        url = r.json()["data"]["image"]["url"]
                        worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, selected_sub, topic_final.strip().title(), notes, "No"])
                        quotes = ["One step closer to 11+ Success! 🌟", "Brilliant! Your future self will thank you. 🎓", "Mistake logged. Mastery incoming! 🚀", "Great job catching that one! ✅"]
                        st.success(random.choice(quotes))
                        st.session_state.upload_reset_counter += 1
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
                with c_title.popover("🖼️ VIEW"):
                    st.image(row['ImageURL'])
                    # --- FEATURE: OPEN IN NEW TAB ---
                    st.markdown(f'<a href="{row["ImageURL"]}" target="_blank" class="open-link">🔗 OPEN FULL IMAGE</a>', unsafe_allow_html=True)
                    st.info(f"Notes: {row['Notes']}")
                
                if c_ask.button("💬 ASK AI", key=f"ask_{row['SheetRow']}", use_container_width=True):
                    st.session_state.active_image = row['ImageURL']
                    st.toast("Sent to AI!")
                is_m = row['Mastered'].strip().upper() == "YES"
                if c_mast.button("✅ DONE" if is_m else "⬜ MARK DONE", key=f"m_{row['SheetRow']}", use_container_width=True):
                    worksheet.update_cell(row['SheetRow'], 6, "Yes" if not is_m else "No")
                    st.rerun()
                with c_del.popover("🗑️ DELETE"):
                    if st.button("CONFIRM DELETE", key=f"del_{row['SheetRow']}", use_container_width=True):
                        worksheet.delete_rows(row['SheetRow']); st.rerun()
    else: st.info("Bank is empty.")

# --- TAB 3: QUIZ ---
with tab3:
    st.markdown("### 🎲 QUICK CHALLENGE")
    if st.button("DRAW RANDOM QUESTION", use_container_width=True, key="quiz_draw"):
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
            # --- FEATURE: OPEN IN NEW TAB ---
            st.markdown(f'<a href="{sel["ImageURL"]}" target="_blank" class="open-link">🔗 OPEN FULL IMAGE</a>', unsafe_allow_html=True)
            st.markdown(f"## {sel['Subject']}: {sel['Topic']}")
            if st.button("💡 GET AI HINT", key="quiz_hint", use_container_width=True):
                st.session_state.active_image = sel['ImageURL']
                hint_p = f"Give me a hint for this {sel['Subject']} question."
                st.session_state.messages.append({"role": "user", "content": hint_p})
                with st.spinner("Asking AI..."):
                    response = chat_with_ai(hint_p, image_url=sel['ImageURL'])
                    st.session_state.messages.append({"role": "assistant", "content": response})
                st.toast("Hint in Sidebar!"); st.rerun()

# --- TAB 4: PROGRESS ---
with tab4:
    st.markdown("### 📊 MASTERY DASHBOARD")
    if len(data) > 1:
        df_p = pd.DataFrame(data[1:], columns=data[0])
        df_p['dt'] = pd.to_datetime(df_p['Timestamp'], errors='coerce')
        total = len(df_p); mastered = len(df_p[df_p['Mastered'].str.upper() == "YES"])
        perc = (mastered/total)*100 if total > 0 else 0
        c1, c2, c3 = st.columns(3); c1.metric("TOTAL LOGS", total); c2.metric("MASTERED", mastered); c3.metric("SUCCESS RATE", f"{perc:.1f}%")
        st.progress(perc/100)
        st.divider()
        st.markdown("### 🗓️ LAST 7 DAYS BY SUBJECT")
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_df = df_p[df_p['dt'] >= seven_days_ago]
        if not recent_df.empty:
            sub_counts = recent_df['Subject'].value_counts()
            for sub, count in sub_counts.items():
                st.write(f"**{sub}**: {count} mistakes logged")
                st.progress(min(count / sub_counts.max(), 1.0))
        else: st.info("No recent logs.")
        st.divider()
        st.markdown("### 📈 TOPIC FREQUENCY ANALYSIS")
        if st.checkbox("Show Topics by Difficulty"):
            topic_counts = df_p['Topic'].value_counts().sort_values(ascending=True)
            st.dataframe(topic_counts, use_container_width=True)
