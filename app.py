import streamlit as st
import pandas as pd
import qrcode
from PIL import Image
import io
import random
import string

# Function to generate a unique Bill ID
def generate_bill_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# Function to calculate bill details
def calculate_bill(bill_type, details):
    subtotal = details['usage'] * details['rate']
    gst = subtotal * 0.18
    total = subtotal + gst
    bill_id = generate_bill_id()

    bill_data = {
        'Bill ID': [bill_id],
        'Customer Name': [details['name']],
        'Bill Type': [bill_type.capitalize()],
        'Usage': [details['usage']],
        'Rate per Unit': [details['rate']],
        'Subtotal': [subtotal],
        'GST (18%)': [gst],
        'Total Amount': [total]
    }

    return pd.DataFrame(bill_data)

# Function to generate UPI QR code
def generate_upi_qr(upi_id, name, amount, note):
    upi_link = f"upi://pay?pa={upi_id}&pn={name}&am={amount:.2f}&cu=INR&tn={note}"
    qr = qrcode.make(upi_link)
    return qr

# Streamlit UI
st.set_page_config(page_title="Government Utility Bill Generator", layout="centered")
st.title("🏛️ Government Utility Bill Generator")

# Bill type selection
bill_type = st.selectbox("Select Bill Type", ["Electricity", "Water", "Gas", "Property Tax", "Other"])

# Input form
with st.form("bill_form"):
    name = st.text_input("Customer Name")
    usage = st.number_input("Usage (e.g., units consumed, area in sq.ft.)", min_value=0.0, step=0.1)
    rate = st.number_input("Rate per Unit", min_value=0.0, step=0.1)
    upi_id = st.text_input("Your UPI ID (e.g., yourname@upi)")
    submitted = st.form_submit_button("Generate Bill")

if submitted:
    if not name or not upi_id:
        st.error("Please provide all required information.")
    else:
        details = {'name': name, 'usage': usage, 'rate': rate}
        bill_df = calculate_bill(bill_type, details)
        st.success("✅ Bill Generated Successfully!")
        st.dataframe(bill_df)

        # Generate and display UPI QR code
        amount = bill_df['Total Amount'][0]
        note = f"{bill_type} Bill Payment"
        qr_image = generate_upi_qr(upi_id, name, amount, note)

        # Display QR code
        st.subheader("Scan to Pay")
        buf = io.BytesIO()
        qr_image.save(buf)
        st.image(buf.getvalue(), width=250)

        # Download options
        csv = bill_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Bill as CSV", csv, f"{bill_type.lower()}_bill.csv", "text/csv")

        buf.seek(0)
        st.download_button("Download UPI QR Code", buf, f"{bill_type.lower()}_upi_qr.png", "image/png")
