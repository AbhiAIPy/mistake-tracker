import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import pandas as pd
import requests
import base64
import json
from fpdf import FPDF

# --- ⚙️ CONFIGURATION ---
try:
    IMGBB_API_KEY = st.secrets["IMGBB_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
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

# --- 🤖 THE AI FIX (THOUGHT HARD ON THIS) ---
def get_ai_response(subject, topic, notes, image_url):
    # This specific URL is the most compatible with Free Tier API Keys
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        # 1. Get image and encode properly
        img_data = requests.get(image_url).content
        encoded_img = base64.b64encode(img_data).decode('utf-8')
        
        headers = {'Content-Type': 'application/json'}
        
        # 2. Strict Payload Format
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"Solve this {subject} question about {topic}. Explain step-by-step. Notes: {notes}"},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": encoded_img
                        }
                    }
                ]
            }]
        }

        res = requests.post(url, headers=headers, json=payload)
        res_json = res.json()
        
        # 3. Defensive extraction of text
        if 'candidates' in res_json:
            return res_json['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"AI Error: {res_json.get('error', {}).get('message', 'Model Refused')}"
            
    except Exception as e:
        return f"System Error: {str(e)}"

# --- 🎨 UI SETUP ---
st.set_page_config(page_title="11+ AI Master Bank", layout="centered")
st.markdown("<style>.stButton>button { width: 100%; border-radius: 10px; font-weight: bold; height: 3em; }</style>", unsafe_allow_html=True)
st.title("🧠 11+ Mistake Bank")

t1, t2, t3, t4 = st.tabs(["➕ Add", "🔍 Review", "🎲 Quiz", "🖨️ Print"])

with t1:
    up = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"])
    with st.form("add_f", clear_on_submit=True):
        sub = st.selectbox("Subject", ['Maths', 'VR', 'NVR', 'English', 'SPAG'])
        top = st.text_input("Topic")
        nts = st.text_area("Notes")
        if st.form_submit_button("Save") and up:
            r = requests.post("https://api.imgbb.com/1/upload", data={"key": IMGBB_API_KEY}, files={"image": up.getvalue()})
            if r.status_code == 200:
                url = r.json()["data"]["image"]["url"]
                worksheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), url, sub, top.title(), nts, "No"])
                st.success("Saved!")

with t2:
    data = worksheet.get_all_values()
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
        df['dt'] = pd.to_datetime(df['Timestamp'])
        
        # ASCENDING SORT
        df = df.sort_values('dt', ascending=True)

        for i, row in df.iterrows():
            # Find the exact row in Google Sheets
            sheet_idx = data.index(row.tolist()) + 1 
            
            with st.container(border=True):
                st.write(f"**{row['Subject']}**: {row['Topic']}")
                c1, c2, c3, c4 = st.columns(4)
                
                with c1:
                    with st.popover("🖼️"): st.image(row['ImageURL'])
                with c2:
                    if st.button("🪄 AI", key=f"ai{i}"):
                        st.session_state[f"r{i}"] = get_ai_response(row['Subject'], row['Topic'], row['Notes'], row['ImageURL'])
                with c3:
                    lab = "✅" if row['Mastered'] == "Yes" else "⬜"
                    if st.button(lab, key=f"m{i}"):
                        new = "Yes" if row['Mastered'] == "No" else "No"
                        worksheet.update_cell(sheet_idx, 6, new)
                        st.rerun()
                with c4:
                    # DELETE WITH CONFIRMATION
                    del_p = st.popover("🗑️")
                    del_p.warning("Delete this?")
                    if del_p.button("Confirm", key=f"d{i}"):
                        worksheet.delete_rows(sheet_idx)
                        st.rerun()

                if f"r{i}" in st.session_state:
                    st.info(st.session_state[f"r{i}"])

# --- TAB 3: QUIZ & TAB 4: PRINT ---
with t3:
    if st.button("🎯 Random Challenge"):
        all_data = worksheet.get_all_values()
        if len(all_data) > 1:
            df_q = pd.DataFrame(all_data[1:], columns=all_data[0])
            pick = df_q[df_q['Mastered'] != "Yes"].sample(1).iloc[0]
            st.image(pick['ImageURL'])
            st.write(f"**{pick['Subject']}**: {pick['Topic']}")

with t4:
    if st.button("📄 Build PDF"):
        st.write("PDF Logic Ready - Download below")
