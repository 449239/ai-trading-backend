import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from datetime import datetime
import time

st.set_page_config(page_title="AI Trading Bot", layout="wide")
st.title("🚀 Advanced AI Trading Signal Bot")

# === USER INPUTS ===
ticker = st.text_input("Enter Ticker", value="AAPL").upper()
account_balance = st.number_input("Account Balance ($)", value=10000)
risk_percent = st.slider("Risk per Trade (%)", 0.5, 5.0, 1.0)
strategy = st.selectbox("Choose Your Strategy", ["Scalping", "Swing Trading", "Breakout"])
auto_refresh = st.checkbox("🔄 Auto-Refresh Every 60 Seconds")
run_backtest = st.checkbox("📈 Run Backtest on Strategy")

# Initialize trade history
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
# Initialize trigger state
if "triggered" not in st.session_state:
    st.session_state.triggered = False

# Fetch data with cache
@st.cache_data(ttl=60)
def get_data(ticker):
    return yf.download(ticker, period="5d", interval="15m")

# Indicator calculations
def calculate_indicators(data):
    ...  # existing indicator code
    return data

def generate_signals(data, strategy):
    ...  # existing signal logic
    return entry, stop, take, confidence, reason, sell_signal, sentiment, support, resistance

def run_backtest(data, strategy):
    ...  # existing backtest logic
    return backtest_summary

def plot_chart(data, entry, stop, take, sell_signal, support, resistance):
    ...  # existing chart code
    return fig

# Trigger button sets state
if st.button("Generate Trade Signal"):
    st.session_state.triggered = True

# Auto-refresh if enabled and after initial trigger
if auto_refresh and st.session_state.triggered:
    time.sleep(60)
    st.experimental_rerun()

# Only run when triggered
if st.session_state.triggered:
    st.audio("https://www.soundjay.com/buttons/sounds/button-3.mp3", autoplay=True)
    data = get_data(ticker)
    if data.empty:
        st.error("No data found.")
    else:
        data = calculate_indicators(data)
        entry, stop, take, confidence, reason, sell_signal, sentiment, support, resistance = generate_signals(data, strategy)
        risk_amount = account_balance * risk_percent / 100
        shares = int(risk_amount / (entry - stop)) if entry - stop > 0 else 0
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.audio("https://www.soundjay.com/buttons/sounds/beep-07.mp3", autoplay=True)
        # Display recommendation
        ...  # existing display code
        # Log and display history
        ...  # existing logging and DataFrame code
        # Backtest results
        if run_backtest:
            st.subheader("📊 Backtest Results")
            st.write(run_backtest(data, strategy))
else:
    st.info("Click 'Generate Trade Signal' to run the analysis and chart.")
