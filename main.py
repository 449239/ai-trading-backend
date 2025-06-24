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

# === State ===
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []

@st.cache_data(ttl=60)
def get_data(ticker):
    return yf.download(ticker, period="5d", interval="15m")

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

def generate_signals(data, strategy):
    last = data.iloc[-1]
    entry = last['Close']
    stop, take, confidence, reason = 0, 0, 50, ""
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
    elif strategy == "Breakout":
        stop = last['BB_lower']
        take = last['BB_upper'] + (last['BB_upper'] - last['BB_lower']) * 0.5
        confidence = 90 if entry > last['BB_upper'] and last['MACD'] > last['Signal_Line'] else 50
        reason = "Breakout above resistance + MACD confirm" if confidence == 90 else "Premature breakout"
    sell_signal = False
    if last['RSI'] > 70 or last['MACD'] < last['Signal_Line']:
        sell_signal = True
    return entry, stop, take, confidence, reason, sell_signal, last['Sentiment'], last['Support'], last['Resistance']

def run_backtest(data, strategy):
    signals = []
    for i in range(20, len(data)):
        slice_data = data.iloc[:i+1]
        entry, stop, take, conf, reason, sell_signal, _, _, _ = generate_signals(slice_data, strategy)
        signals.append({"entry": entry, "stop": stop, "take": take, "sell": sell_signal})
    wins = [1 for s in signals if s['take'] > s['entry'] and not s['sell']]
    losses = [1 for s in signals if s['stop'] < s['entry']]
    win_rate = len(wins) / max(1, (len(wins) + len(losses)))
    return f"Win Rate: {win_rate:.2%} from {len(signals)} trades"

def plot_chart(data, entry, stop, take, sell_signal, support, resistance):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'],
                                 low=data['Low'], close=data['Close'], name='Price'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], mode='lines', name='EMA20'))
    fig.add_trace(go.Scatter(x=data.index, y=data['EMA50'], mode='lines', name='EMA50'))
    for idx in data['Gap_Fill'].dropna().index:
        gap_price = data.loc[idx, 'Open']
        fig.add_shape(type="line", x0=idx, x1=idx, y0=gap_price, y1=gap_price,
                      line=dict(color="purple", width=1, dash="dot"))
        fig.add_annotation(x=idx, y=gap_price, text="Gap", showarrow=False, yshift=10, font=dict(color="purple"))
    for idx in data.index:
        color = 'lightgreen' if data.loc[idx, 'Sentiment'] == 'Bullish' else ('lightcoral' if data.loc[idx, 'Sentiment'] == 'Bearish' else None)
        if color:
            fig.add_vrect(x0=idx, x1=idx, fillcolor=color, opacity=0.1, line_width=0)
    fig.add_shape(type="line", x0=data.index[0], x1=data.index[-1], y0=support, y1=support,
                  line=dict(color="green", width=1, dash="dash"))
    fig.add_shape(type="line", x0=data.index[0], x1=data.index[-1], y0=resistance, y1=resistance,
                  line=dict(color="red", width=1, dash="dash"))
    fig.add_trace(go.Scatter(x=[data.index[-1]], y=[entry], mode='markers+text',
                             marker=dict(color='green', size=10), text=["Entry"], name='Entry'))
    fig.add_trace(go.Scatter(x=[data.index[-1]], y=[stop], mode='markers+text',
                             marker=dict(color='red', size=10), text=["Stop"], name='Stop Loss'))
    fig.add_trace(go.Scatter(x=[data.index[-1]], y=[take], mode='markers+text',
                             marker=dict(color='blue', size=10), text=["TP"], name='Take Profit'))
    if sell_signal:
        fig.add_trace(go.Scatter(x=[data.index[-1]], y=[entry], mode='markers+text',
                                 marker=dict(color='orange', size=12), text=["SELL"], name='Sell Signal'))
    fig.update_layout(title=f"{ticker} - Trading Chart", xaxis_title="Time", yaxis_title="Price")
    return fig

while True:
    data = get_data(ticker)
    if not data.empty:
        data = calculate_indicators(data)
        entry, stop, take, confidence, reason, sell_signal, sentiment, support, resistance = generate_signals(data, strategy)
        risk_amount = account_balance * (risk_percent / 100)
        risk_per_share = entry - stop
        shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        st.subheader("🧠 Trade Recommendation")
        st.write(f"Strategy: {strategy}")
        st.write(f"Signal: {'SELL' if sell_signal else 'BUY'}")
        st.write(f"Entry Price: ${entry:.2f}")
        st.write(f"Stop Loss: ${stop:.2f}")
        st.write(f"Take Profit: ${take:.2f}")
        st.write(f"Position Size: {shares} shares")
        st.write(f"Confidence Score: {confidence}%")
        st.info(f"Reason: {reason}")
        st.info(f"Sentiment: {sentiment}")
        st.plotly_chart(plot_chart(data, entry, stop, take, sell_signal, support, resistance), use_container_width=True)

        st.session_state.trade_history.append({
            "Time": timestamp,
            "Ticker": ticker,
            "Strategy": strategy,
            "Signal": "SELL" if sell_signal else "BUY",
            "Entry": round(entry, 2),
            "Stop": round(stop, 2),
            "Take": round(take, 2),
            "Shares": shares,
            "Confidence": confidence,
            "Reason": reason,
            "Sentiment": sentiment,
            "Status": "Open"
        })
        st.subheader("📜 Trade History")
        st.dataframe(pd.DataFrame(st.session_state.trade_history), use_container_width=True)
        if run_backtest:
            st.subheader("📊 Backtest Results")
            st.write(run_backtest(data, strategy))
    if not auto_refresh:
        break
    time.sleep(60)
