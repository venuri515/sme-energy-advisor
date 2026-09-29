"""Streamlit dashboard for SME Energy Advisor. Talks to the FastAPI backend over HTTP."""
import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="SME Energy Advisor", layout="wide")
st.title("⚡ SME Energy Advisor")


def get_businesses():
    response = requests.get(f"{API_URL}/businesses")
    response.raise_for_status()
    return response.json()


def create_business(name: str, category: str):
    response = requests.post(f"{API_URL}/businesses", json={"name": name, "category": category})
    response.raise_for_status()
    return response.json()


def get_bills(business_id: int):
    response = requests.get(f"{API_URL}/bills", params={"business_id": business_id})
    response.raise_for_status()
    return response.json()


def create_bill(business_id: int, bill_date: str, kwh: float, submitted_amount: float | None):
    payload = {"business_id": business_id, "bill_date": bill_date, "kwh": kwh}
    if submitted_amount:
        payload["submitted_amount"] = submitted_amount
    response = requests.post(f"{API_URL}/bills", json=payload)
    response.raise_for_status()
    return response.json()


def get_carbon(bill_id: int):
    response = requests.get(f"{API_URL}/bills/{bill_id}/carbon")
    response.raise_for_status()
    return response.json()


def get_savings(bill_id: int):
    response = requests.get(f"{API_URL}/bills/{bill_id}/savings")
    response.raise_for_status()
    return response.json()

def get_forecast(business_id: int):
    response = requests.get(f"{API_URL}/businesses/{business_id}/forecast")
    if response.status_code == 400:
        return None
    response.raise_for_status()
    return response.json()


# --- Sidebar: pick or create a business ---
st.sidebar.header("Business")

try:
    businesses = get_businesses()
except requests.exceptions.ConnectionError:
    st.error("Can't reach the API. Make sure it's running: `uvicorn app.api.main:app --reload`")
    st.stop()

business_names = {b["name"]: b for b in businesses}
options = ["-- New business --"] + list(business_names.keys())
default_index = options.index(st.session_state.get("selected_business_name", options[0])) if st.session_state.get("selected_business_name") in options else 0
choice = st.sidebar.selectbox("Select a business", options, index=default_index)
if choice == "-- New business --":
    with st.sidebar.form("new_business"):
        name = st.text_input("Business name")
        category = st.selectbox("Tariff category", ["general_purpose", "industrial", "hotel"])
        submitted = st.form_submit_button("Create")
        if submitted and name:
            new_business = create_business(name, category)
            st.session_state["selected_business_name"] = new_business["name"]
            st.rerun()
    st.info("Create a business in the sidebar to get started.")
    st.stop()

business = business_names[choice]
st.subheader(f"{business['name']} ({business['category'].replace('_', ' ').title()})")

# --- Add a bill ---
with st.expander("Add a bill", expanded=True):
    with st.form("new_bill"):
        col1, col2, col3 = st.columns(3)
        bill_date = col1.date_input("Bill date")
        kwh = col2.number_input("kWh used", min_value=0.0, step=1.0)
        submitted_amount = col3.number_input("Submitted amount (LKR, optional)", min_value=0.0, step=1.0)
        submitted = st.form_submit_button("Add bill")
        if submitted:
            create_bill(business["id"], str(bill_date), kwh, submitted_amount or None)
            st.success("Bill added")
            st.rerun()

# --- Bills table ---
bills = get_bills(business["id"])

if not bills:
    st.info("No bills yet. Add one above.")
    st.stop()

st.subheader("Bills")
table_data = [
    {
        "Date": b["bill_date"],
        "kWh": b["kwh"],
        "Calculated (LKR)": b["calculated_amount"],
        "Submitted (LKR)": b["submitted_amount"],
        "Mismatch (LKR)": b["mismatch"],
    }
    for b in bills
]
st.dataframe(table_data, use_container_width=True)

# --- Chart: consumption over time ---
st.subheader("Consumption over time")
st.line_chart({"kWh": [b["kwh"] for b in bills]})

# --- Carbon and savings for the latest bill ---
latest_bill = bills[-1]
st.subheader(f"Latest bill: {latest_bill['bill_date']}")

col1, col2 = st.columns(2)

with col1:
    carbon = get_carbon(latest_bill["id"])
    st.metric("Estimated carbon", f"{carbon['carbon_kg']:.1f} kg CO₂")

with col2:
    savings = get_savings(latest_bill["id"])
    st.write("**Savings suggestions:**")
    if not savings["suggestions"]:
        st.write("No suggestions right now — usage looks steady.")
    for s in savings["suggestions"]:
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}[s["priority"]]
        st.write(f"{icon} **{s['title']}** — {s['detail']}")

# --- Forecast ---
st.subheader("Next month's forecast")
forecast = get_forecast(business["id"])
if forecast is None:
    st.info("Add at least 2 bills to see a forecast.")
else:
    st.metric("Predicted next month", f"{forecast['predicted_kwh']:.0f} kWh")
    st.caption(f"Based on a linear trend over the last {forecast['based_on_months']} months.")