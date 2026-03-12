import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
from anthropic import Anthropic

# --- ⚙️ CONFIGURATION ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    CLAUDE_API_KEY = st.secrets["CLAUDE_API_KEY"]
    client = Anthropic(api_key=CLAUDE_API_KEY)
except Exception as e:
    st.error("Secrets missing! Please add CLAUDE_API_KEY to your Streamlit secrets.")
    st.stop()

# --- 🛡️ AUTHENTICATION ---
def get_creds():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    return Credentials.from_service_account_info(creds_dict, scopes=scope)

gc = gspread.authorize(get_creds())
sh = gc.open("Study Mistake Log")
worksheet = sh.worksheet("Mistakes")

# --- 🧠 CLAUDE VISION FUNCTION ---
def get_claude_response(image_url, subject, topic, notes):
    try:
        # Fetch image and convert to base64
        img_response = requests.get(image_url)
        base64_image = base64.b64encode(img_response.content).decode("utf-8")
        
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": base64_image}
                    },
                    {
                        "type": "text", 
                        "text": f"Study Helper: This is a {subject} mistake about {topic}. My notes: {notes}. Look at the image, explain why it's tricky, and give me a similar practice question with steps."
                    }
                ]
            }]
        )
        return message.content[0].text
    except Exception as e:
        return f"Claude Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ Master Bank", layout="centered")
st.markdown("<style>.date-label { font-size: 11px; color: #94a3b8; }</style>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["➕ Add", "🔍 Review"])

# --- TAB 1: ADD ---
with tab1:
    uploaded_file = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])
    with st.form("add_form", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English'])
        top = st.text_input("Topic")
        nts = st.text_area("Notes")
        if st.form_submit_button("🚀 Save"):
            res = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": uploaded_file.getvalue()})
            if res.status_code == 200:
                url = res.json()["data"]["image"]["url"]
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, top, nts, "No"])
                st.success("Saved!")

# --- TAB 2: REVIEW ---
with tab2:
    all_rows = worksheet.get_all_values()
    if len(all_rows) > 1:
        df = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        df['dt_obj'] = pd.to_datetime(df['Timestamp'])
        
        # FILTERS
        search = st.text_input("🔍 Search Topic or Notes")
        show_mastered = st.toggle("Show Mastered", value=False)
        
        # LOGIC
        filtered = df.copy()
        if not show_mastered: filtered = filtered[filtered['Mastered'].str.upper() != "YES"]
        if search:
            filtered = filtered[filtered['Topic'].str.contains(search, case=False) | filtered['Notes'].str.contains(search, case=False)]
        
        # ASCENDING SORT
        filtered = filtered.sort_values(by='dt_obj', ascending=True)

        for index, row in filtered.iterrows():
            with st.container(border=True):
                st.markdown(f"<div class='date-label'>📅 Logged: {row['Timestamp']}</div>", unsafe_allow_html=True)
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                
                c1, c2 = st.columns(2)
                with c1: st.image(row['ImageURL'])
                with c2:
                    if st.button("🪄 Claude AI", key=f"ai_{index}"):
                        with st.spinner("Claude is looking..."):
                            st.session_state[f"res_{index}"] = get_claude_response(row['ImageURL'], row['Subject'], row['Topic'], row['Notes'])
                
                if f"res_{index}" in st.session_state:
                    st.info(st.session_state[f"res_{index}"])
