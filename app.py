import streamlit as st
import openai
import sqlite3
import os
import pandas as pd
from dotenv import load_dotenv
import qrcode
from PIL import Image
import io
import fitz  # PyMuPDF

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bills.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
                 username TEXT PRIMARY KEY,
                 password TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bills (
                 username TEXT,
                 bill_type TEXT,
                 amount TEXT,
                 status TEXT,
                 upi_id TEXT)""")
    conn.commit()
    conn.close()

init_db()

# --- USER MANAGEMENT ---
def register_user(username, password):
    conn = sqlite3.connect("bills.db")
    c = conn.cursor()
    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

def login_user(username, password):
    conn = sqlite3.connect("bills.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    result = c.fetchone()
    conn.close()
    return result

# --- AI BILL PARSER ---
def parse_bill_text(text):
    prompt = f"""
Extract the following details from this bill text:
- Bill type
- Amount
- UPI ID (or 'Not Available')

Here is the text:
{text}

Return JSON like:
{{"bill_type": "...", "amount": "...", "upi_id": "..."}}"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Azure model name
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    import json
    return json.loads(response.choices[0].message.content.strip())

# --- QR GENERATION ---
def generate_qr(upi_id, amount, note="Bill Payment"):
    upi_link = f"upi://pay?pa={upi_id}&am={amount}&tn={note}"
    qr = qrcode.make(upi_link)
    return qr

# --- EXTRACT TEXT FROM FILE ---
def extract_text(file):
    if file.type == "application/pdf":
        text = ""
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text
    elif file.type.startswith("text") or file.type.endswith(".csv"):
        return file.read().decode("utf-8")
    else:
        return "Unsupported file type"

# --- NOTIFICATION (SENDGRID) ---
def send_email(to_email, subject, message):
    import requests
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": FROM_EMAIL},
        "subject": subject,
        "content": [{"type": "text/plain", "value": message}],
    }
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }
    r = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers)
    return r.status_code == 202

# --- STREAMLIT UI ---
st.set_page_config("💡Gov Bill Payment Agent", layout="centered")
st.title("🏛️ Government Bill Payment Agent (AI + UPI + Azure)")

# Session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# --- LOGIN/REGISTER FORM ---
if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])

    with tab1:
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if login_user(user, pwd):
                st.session_state.logged_in = True
                st.session_state.username = user
                st.success("✅ Logged in successfully!")
            else:
                st.error("❌ Invalid credentials")

    with tab2:
        new_user = st.text_input("New Username")
        new_pwd = st.text_input("New Password", type="password")
        if st.button("Register"):
            try:
                register_user(new_user, new_pwd)
                st.success("🎉 Registered successfully! Please login.")
            except:
                st.error("⚠️ Username might already exist.")

else:
    st.subheader(f"Welcome, {st.session_state.username} 👋")

    uploaded = st.file_uploader("📄 Upload your bill (PDF, TXT, CSV)", type=["pdf", "txt", "csv"])
    if uploaded:
        st.success("File uploaded successfully.")
        raw_text = extract_text(uploaded)
        st.text_area("📜 Extracted Text", raw_text, height=150)

        if st.button("🧠 Parse & Generate QR"):
            with st.spinner("AI is extracting bill details..."):
                bill = parse_bill_text(raw_text)

            st.json(bill)

            qr_img = generate_qr(bill['upi_id'], bill['amount'], bill['bill_type'])
            st.image(qr_img, caption="Scan to Pay with UPI")

            # Save to DB
            conn = sqlite3.connect("bills.db")
            c = conn.cursor()
            c.execute("INSERT INTO bills (username, bill_type, amount, status, upi_id) VALUES (?, ?, ?, ?, ?)",
                      (st.session_state.username, bill["bill_type"], bill["amount"], "Pending", bill["upi_id"]))
            conn.commit()
            conn.close()

            # Simulate payment + notify
            if st.button("✅ Mark as Paid & Notify"):
                conn = sqlite3.connect("bills.db")
                c = conn.cursor()
                c.execute("UPDATE bills SET status='Paid' WHERE username=? AND bill_type=?", 
                          (st.session_state.username, bill["bill_type"]))
                conn.commit()
                conn.close()

                if send_email(st.session_state.username + "@example.com", 
                              "✅ Bill Payment Success", 
                              f"You've paid ₹{bill['amount']} for {bill['bill_type']}."):
                    st.success("💌 Notification sent successfully!")
                else:
                    st.warning("⚠️ Notification failed.")

    # Show history
    if st.checkbox("📜 Show My Bill History"):
        conn = sqlite3.connect("bills.db")
        df = pd.read_sql_query("SELECT * FROM bills WHERE username=?", conn, params=(st.session_state.username,))
        st.dataframe(df)

    if st.button("🔒 Logout"):
        st.session_state.logged_in = False
        st.experimental_rerun()
