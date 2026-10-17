"""Glass-style Streamlit screen for the SME Energy Advisor.

Keep this file in the project root (next to the app/ and agent/ folders) and run:
    streamlit run glass_app.py

"Check a bill" calls the tariff engine directly, so it needs no API or database.
"Ask the advisor" needs the agent environment (.venv-agent) and AWS credentials.
"""
import sys
from datetime import date
from pathlib import Path

# Project root first, so `app` means the app/ package and never dashboard/app.py
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from app.forecasting.baseline import forecast_next_month
from app.recommendations.rules import generate_suggestions
from app.tariff_engine.calculator import calculate_bill
from app.tariff_engine.carbon import calculate_carbon_kg
from app.tariff_engine.loader import load_tariff_for_date

st.set_page_config(page_title="SME Energy Advisor", page_icon="⚡", layout="wide")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700&family=Manrope:wght@400;500;600&display=swap');
:root{--glass:rgba(255,255,255,.12);--edge:rgba(255,255,255,.24);--ink:#eef4fb;--mute:#a9bdd3;--amber:#f2b36b;--mint:#7fe0c3;}
html,body,.stApp,.stApp *{font-family:'Manrope',sans-serif;}
.stApp{color:var(--ink);background:
 radial-gradient(60rem 40rem at 6% 4%,rgba(38,148,168,.55),transparent 60%),
 radial-gradient(50rem 38rem at 96% 10%,rgba(90,82,214,.45),transparent 62%),
 radial-gradient(55rem 40rem at 70% 108%,rgba(242,179,107,.30),transparent 60%),
 radial-gradient(34rem 26rem at 66% 30%,rgba(242,179,107,.26),transparent 65%),#06142a;
 background-attachment:fixed;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{max-width:1150px;padding-top:2.5rem;}
h1,h2,h3{font-family:'Bricolage Grotesque',sans-serif!important;letter-spacing:-.025em;color:var(--ink);}
h1{font-size:3rem!important;font-weight:700;line-height:1.05;}
[data-testid="stCaptionContainer"],label,.stMarkdown p{color:var(--mute);}
div[data-testid="stVerticalBlockBorderWrapper"]{background:var(--glass);border:1px solid var(--edge);
 border-radius:22px;backdrop-filter:blur(20px) saturate(140%);-webkit-backdrop-filter:blur(20px) saturate(140%);
 box-shadow:0 18px 50px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.22);padding:.4rem .6rem;}
[data-testid="stMetric"]{background:var(--glass);border:1px solid var(--edge);border-radius:16px;padding:.8rem 1rem;
 backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);}
[data-testid="stMetricValue"]{color:var(--ink);font-family:'Bricolage Grotesque',sans-serif;font-size:1.7rem!important;}
[data-testid="stMetricValue"] div{overflow:visible!important;text-overflow:clip!important;white-space:normal!important;}
[data-testid="stMetricLabel"]{color:var(--mute);}
[data-testid="stMetricLabel"] div,[data-testid="stMetricLabel"] p{overflow:visible!important;text-overflow:clip!important;white-space:normal!important;}
div[data-baseweb="input"],div[data-baseweb="select"]>div,div[data-baseweb="base-input"]{background:rgba(255,255,255,.07)!important;
 border-color:var(--edge)!important;border-radius:12px!important;}
input,textarea{color:var(--ink)!important;}
.stTabs [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--edge);}
.stTabs [data-baseweb="tab"]{color:var(--mute);border-radius:12px 12px 0 0;padding:.6rem 1.1rem;}
.stTabs [aria-selected="true"]{color:var(--ink);background:var(--glass);}
[data-testid="stChatMessage"]{background:var(--glass);border:1px solid var(--edge);border-radius:18px;
 backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);}
.big{font-family:'Bricolage Grotesque',sans-serif;font-size:4.2rem;font-weight:700;line-height:1;letter-spacing:-.03em;color:var(--mint);}
.big.warn{color:var(--amber);}
.verdict{font-size:1.1rem;color:var(--ink);margin:.4rem 0 .8rem;}
.tip{border-left:3px solid var(--amber);padding:.1rem 0 .1rem .8rem;margin:.7rem 0;color:var(--ink);}
.tip b{display:block;margin-bottom:.15rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.title("Is your electricity bill right?")
st.caption("Check a Sri Lankan business bill against the official tariff, see its carbon cost, and find ways to save.")

tab_check, tab_ask = st.tabs(["Check a bill", "Ask the advisor"])

with tab_check:
    left, right = st.columns([1, 1.3], gap="large")

    with left, st.container(border=True):
        category = st.selectbox(
            "Business type",
            ["general_purpose", "industrial", "hotel"],
            format_func=lambda c: c.replace("_", " ").title(),
        )
        month = st.date_input("Billing month", value=date(2026, 6, 1))
        kwh = st.number_input("Units used (kWh)", min_value=0.0, value=190.0, step=1.0)
        charged = st.number_input("Amount charged (LKR)", min_value=0.0, value=9000.0, step=100.0)
        history_text = st.text_input("Earlier months in kWh, oldest first (optional)", placeholder="150, 170, 185")

    try:
        earlier = [float(x) for x in history_text.split(",") if x.strip()]
    except ValueError:
        earlier = []
        left.warning("Earlier months should be numbers separated by commas.")

    tariff = load_tariff_for_date(month)
    result = calculate_bill(category, kwh, tariff)
    diff = charged - result.total
    series = earlier + [kwh]

    with right:
        with st.container(border=True):
            st.markdown("Official bill for this usage")
            over = diff > 1
            st.markdown(f'<div class="big {"warn" if over else ""}">LKR {result.total:,.0f}</div>', unsafe_allow_html=True)
            if abs(diff) <= 1:
                verdict = "Your bill matches the tariff."
            elif over:
                verdict = f"You were charged LKR {diff:,.0f} more than the tariff says."
            else:
                verdict = f"You were charged LKR {-diff:,.0f} less than the tariff says."
            st.markdown(f'<div class="verdict">{verdict}</div>', unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("CO₂ this month", f"{calculate_carbon_kg(kwh):,.0f} kg")
            c2.metric("Rate band", "Higher" if result.band_used == "high" else "Lower")
            if len(series) >= 2:
                c3.metric("Next month", f"{forecast_next_month(series).predicted_kwh:,.0f} kWh")
            else:
                c3.metric("Next month (add history)", "–")

        with st.container(border=True):
            st.markdown("**Ways to save**")
            tips = generate_suggestions(
                kwh=kwh,
                category=category,
                tariff=tariff,
                recent_kwh=series if len(series) >= 3 else None,
                mismatch=result.total - charged,
                calculated_amount=result.total,
            )
            if not tips:
                st.markdown("No quick wins found for this month.")
            for t in tips:
                st.markdown(f'<div class="tip"><b>{t.title}</b>{t.detail}</div>', unsafe_allow_html=True)

with tab_ask:
    @st.cache_resource
    def load_agent():
        from agent.main import agent
        return agent

    if "chat" not in st.session_state:
        st.session_state.chat = []

    for role, text in st.session_state.chat:
        with st.chat_message(role):
            st.markdown(text)

    prompt = st.chat_input("Describe your bill, for example: 190 kWh in June 2026, charged 9,000 rupees")
    if prompt:
        st.session_state.chat.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Checking the tariff..."):
                    reply = str(load_agent()(prompt))
            except Exception as e:  # show the real reason instead of a blank screen
                reply = f"The advisor could not answer: {e}. Run this from .venv-agent and check your AWS sign-in."
            st.markdown(reply)
        st.session_state.chat.append(("assistant", reply))