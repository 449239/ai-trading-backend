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
import traceback

# === Page Config ===
st.set_page_config(page_title="AI Trading Bot", layout="wide")
st.title("🚀 Advanced AI Trading Signal Bot")

# === State Initialization ===
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []
if "ticker" not in st.session_state:
    st.session_state.ticker = "AAPL"
if "account_balance" not in st.session_state:
    st.session_state.account_balance = 10000
if "risk_percent" not in st.session_state:
    st.session_state.risk_percent = 1.0
if "strategy" not in st.session_state:
    st.session_state.strategy = "Scalping"
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "run_backtest" not in st.session_state:
    st.session_state.run_backtest = False

# === Cached Data Fetching ===
@st.cache_data(ttl=60)
def get_data(ticker):
    return yf.download(ticker, period="5d", interval="15m")

# === Indicator Calculations ===
def calculate_indicators(data):
    data['RSI'] = RSIIndicator(data['Close']).rsi()
    data['EMA20'] = EMAIndicator(data['Close'], window=20).ema_indicator()
    data['EMA50'] = EMAIndicator(data['Close'], window=50).ema_indicator()
    macd = MACD(data['Close'])
    data['MACD'] = macd.macd()
    data['Signal_Line'] = macd.macd_signal()
    bb = BollingerBands(data['Close'])
    data['BB_upper'] = bb.bollinger_hband()
    data['BB_lower'] = bb.bollinger_lband()
    data['ATR'] = AverageTrueRange(data['High'], data['Low'], data['Close']).average_true_range()
    data['Gap'] = data['Open'] - data['Close'].shift(1)
    data['Gap_Fill'] = np.where((data['Gap'].abs() > data['ATR']), data['Gap'], np.nan)
    data['Sentiment'] = np.where(
        (data['EMA20'] > data['EMA50']) & (data['RSI'] > 50), 'Bullish',
        np.where((data['EMA20'] < data['EMA50']) & (data['RSI'] < 50), 'Bearish', 'Neutral')
    )
    data['Support'] = data['Low'].rolling(window=20).min()
    data['Resistance'] = data['High'].rolling(window=20).max()
    data.dropna(inplace=True)
    return data

# === Signal Generation ===
def generate_signals(data, strategy):
    last = data.iloc[-1]
    entry = last['Close']
    if strategy == "Scalping":
        stop = entry - last['ATR'] * 0.8
        take = entry + last['ATR'] * 1.2
        confidence = 80 if last['RSI'] < 30 and last['MACD'] > last['Signal_Line'] else 60
        reason = "RSI Oversold + MACD bullish" if confidence == 80 else "Weak signal"
    elif strategy == "Swing Trading":
        stop = entry - last['ATR']
        take = entry + last['ATR'] * 2
        confidence = 85 if last['EMA20'] > last['EMA50'] and last['MACD'] > last['Signal_Line'] else 55
        reason = "EMA trend up + MACD crossover" if confidence == 85 else "Unconfirmed trend"
    else:  # Breakout
        stop = last['BB_lower']
        take = last['BB_upper'] + (last['BB_upper'] - last['BB_lower']) * 0.5
        confidence = 90 if entry > last['BB_upper'] and last['MACD'] > last['Signal_Line'] else 50
        reason = "Breakout above resistance + MACD confirm" if confidence == 90 else "Premature breakout"
    sell_signal = last['RSI'] > 70 or last['MACD'] < last['Signal_Line']
    sentiment = last['Sentiment']
    support = last['Support']
    resistance = last['Resistance']
    return entry, stop, take, confidence, reason, sell_signal, sentiment, support, resistance

# === Backtesting ===
def run_backtest(data, strategy):
    signals = []
    for i in range(20, len(data)):
        slice_data = data.iloc[:i+1]
        e, s, t, *_ = generate_signals(slice_data, strategy)
        signals.append((e, s, t))
    wins = sum(1 for e, s, t in signals if t > e)
    losses = sum(1 for e, s, t in signals if s < e)
    if wins + losses == 0:
        return "No valid backtest signals."
    win_rate = wins / (wins + losses)
    return f"Win Rate: {win_rate:.2%} from {len(signals)} trades"

# === Chart Plotting ===
def plot_chart(data, entry, stop, take, sell_signal, support, resistance):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close']))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], mode='lines', name='EMA20'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA50'], mode='lines', name='EMA50'))
    for idx in data['Gap_Fill'].dropna().index:
        gp = data.loc[idx, 'Open']
        fig.add_shape(type='line', x0=idx, x1=idx, y0=gp, y1=gp, line=dict(color='purple', dash='dot'))
        fig.add_annotation(x=idx, y=gp, text="Gap", showarrow=False, yshift=10, font=dict(color="purple"))
    for idx in data.index:
        col = 'lightgreen' if data.loc[idx,'Sentiment']=='Bullish' else ('lightcoral' if data.loc[idx,'Sentiment']=='Bearish' else None)
        if col:
            fig.add_vrect(x0=idx, x1=idx, fillcolor=col, opacity=0.1, line_width=0)
    fig.add_hline(y=support, line_dash='dash', line_color='green')
    fig.add_hline(y=resistance, line_dash='dash', line_color='red')
    fig.add_trace(go.Scatter(x=[data.index[-1]], y=[entry], mode='markers+text', marker=dict(color='green', size=10), text=['Entry']))
    fig.add_trace(go.Scatter(x=[data.index[-1]], y=[stop], mode='markers+text', marker=dict(color='red', size=10), text=['Stop']))
    fig.add_trace(go.Scatter(x=[data.index[-1]], y=[take], mode='markers+text', marker=dict(color='blue', size=10), text=['TP']))
    if sell_signal:
        fig.add_trace(go.Scatter(x=[data.index[-1]], y=[entry], mode='markers+text', marker=dict(color='orange', size=12), text=['SELL']))
    fig.update_layout(title=f"{st.session_state.ticker} Chart", xaxis_title='Time', yaxis_title='Price')
    return fig

# === Input Form ===
with st.form("trade_form"):
    ticker = st.text_input("Enter Ticker", value=st.session_state.ticker).upper()
    account_balance = st.number_input("Account Balance ($)", value=st.session_state.account_balance)
    risk_percent = st.slider("Risk per Trade (%)", 0.5, 5.0, value=st.session_state.risk_percent)
    strategy = st.selectbox("Choose Your Strategy", ["Scalping", "Swing Trading", "Breakout"], index=["Scalping","Swing Trading","Breakout"].index(st.session_state.strategy))
    auto_refresh = st.checkbox("🔄 Auto-Refresh Every 60 Seconds", value=st.session_state.auto_refresh)
    run_backtest = st.checkbox("📈 Run Backtest on Strategy", value=st.session_state.run_backtest)
    submit = st.form_submit_button("Generate Trade Signal")

if submit:
    st.session_state.ticker = ticker
    st.session_state.account_balance = account_balance
    st.session_state.risk_percent = risk_percent
    st.session_state.strategy = strategy
    st.session_state.auto_refresh = auto_refresh
    st.session_state.run_backtest = run_backtest

    try:
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
            st.subheader("🧠 Trade Recommendation")
            st.write(f"Strategy: {strategy}")
            st.write(f"Signal: {'SELL' if sell_signal else 'BUY'}")
            st.write(f"Entry: ${entry:.2f} | Stop: ${stop:.2f} | TP: ${take:.2f}")
            st.write(f"Size: {shares} | Confidence: {confidence}%")
            st.info(f"Reason: {reason}")
            st.info(f"Sentiment: {sentiment}")
            st.session_state.trade_history.append({
                'Time': timestamp, 'Ticker': ticker, 'Strategy': strategy,
                'Signal': 'SELL' if sell_signal else 'BUY', 'Entry': round(entry,2),
                'Stop': round(stop,2), 'TP': round(take,2), 'Shares': shares,
                'Confidence': confidence, 'Reason': reason, 'Sentiment': sentiment, 'Status':'Open'
            })
            st.plotly_chart(plot_chart(data, entry, stop, take, sell_signal, support, resistance), use_container_width=True)
            st.subheader("📜 Trade History")
            st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)
            if run_backtest:
                st.subheader("📊 Backtest Results")
                st.write(run_backtest(data, strategy))
    except Exception:
        st.error("An error occurred:")
        st.text(traceback.format_exc())
else:
    st.info("Complete the form and click 'Generate Trade Signal' to run the analysis.")

