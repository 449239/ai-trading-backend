from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fastapi.responses import HTMLResponse
from plotly.io import to_html
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
import threading
import time
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_signal = {}
auto_refresh_enabled = True
trade_history = []
open_position = None

user_preferences = {
    "show_hidden_valley": True,
    "show_stop_loss": True,
    "show_take_profit": True,
    "show_short_positions": True,
    "interactive_chart": True
}

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
    global open_position, trade_history
    last = data.iloc[-1]
    entry = last['Close']
    timestamp = datetime.utcnow().isoformat()
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
    else:
        stop = last['BB_lower']
        take = last['BB_upper'] + (last['BB_upper'] - last['BB_lower']) * 0.5
        confidence = 90 if entry > last['BB_upper'] and last['MACD'] > last['Signal_Line'] else 50
        reason = "Breakout above resistance + MACD confirm" if confidence == 90 else "Premature breakout"
    signal_type = "SELL" if last['RSI'] > 70 or last['MACD'] < last['Signal_Line'] else "BUY"
    result = {
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "take": round(take, 2),
        "confidence": confidence,
        "reason": reason,
        "signal": signal_type,
        "sentiment": last['Sentiment'],
        "support": round(last['Support'], 2),
        "resistance": round(last['Resistance'], 2),
        "timestamp": timestamp
    }
    if open_position and signal_type == "SELL":
        open_position['exit_price'] = round(entry, 2)
        open_position['exit_time'] = timestamp
        open_position['pnl'] = round(entry - open_position['entry'], 2)
        open_position['pnl_percent'] = round((entry - open_position['entry']) / open_position['entry'] * 100, 2)
        trade_history.append(open_position)
        open_position = None
    elif not open_position and signal_type == "BUY":
        open_position = {
            "entry": round(entry, 2),
            "entry_time": timestamp,
            "strategy": strategy,
            "ticker": data.index.name,
            "stop": round(stop, 2),
            "take": round(take, 2)
        }
    return result

@app.get("/api/chart")
def get_chart(ticker: str = Query(...)):
    try:
        data = yf.download(ticker, period="5d", interval="15m")
        if data.empty:
            return {"error": "No data found for ticker."}
        data = calculate_indicators(data)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'], high=data['High'], low=data['Low'], close=data['Close'],
            name='Candles'))
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA20'], mode='lines', name='EMA20'))
        fig.add_trace(go.Scatter(x=data.index, y=data['EMA50'], mode='lines', name='EMA50'))
        if user_preferences['show_hidden_valley']:
            fig.add_trace(go.Scatter(x=data.index, y=data['Gap_Fill'], mode='markers', marker=dict(color='orange', size=6), name='Gap Fill'))
        fig.add_trace(go.Scatter(x=data.index, y=data['Support'], mode='lines', name='Support', line=dict(dash='dot')))
        fig.add_trace(go.Scatter(x=data.index, y=data['Resistance'], mode='lines', name='Resistance', line=dict(dash='dot')))
        if open_position:
            fig.add_trace(go.Scatter(x=[open_position['entry_time']], y=[open_position['entry']], mode='markers+text', marker=dict(size=10, color='green'), text=["BUY"], name='Open Trade'))
            if user_preferences['show_stop_loss']:
                fig.add_shape(type='line', x0=data.index[0], x1=data.index[-1], y0=open_position['stop'], y1=open_position['stop'], line=dict(color='red', dash='dash'))
            if user_preferences['show_take_profit']:
                fig.add_shape(type='line', x0=data.index[0], x1=data.index[-1], y0=open_position['take'], y1=open_position['take'], line=dict(color='blue', dash='dash'))
        fig.update_layout(title=f"{ticker} Chart with Indicators", xaxis_title="Time", yaxis_title="Price")
        if user_preferences['interactive_chart']:
            return HTMLResponse(content=to_html(fig, include_plotlyjs='cdn'), status_code=200)
        else:
            return {"error": "Interactive chart disabled."}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/set-preference")
def set_user_preference(key: str, value: bool):
    if key in user_preferences:
        user_preferences[key] = value
    return user_preferences

@app.get("/api/signal")
def get_signal(ticker: str = Query(...), strategy: str = Query("Scalping")):
    try:
        data = yf.download(ticker, period="5d", interval="15m")
        if data.empty:
            return {"error": "No data found for ticker."}
        data = calculate_indicators(data)
        signal = generate_signals(data, strategy)
        latest_signal[ticker] = signal
        return signal
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/toggle-refresh")
def toggle_auto_refresh(state: str = Query("on")):
    global auto_refresh_enabled
    auto_refresh_enabled = state.lower() == "on"
    return {"auto_refresh": auto_refresh_enabled}

@app.get("/api/trade-history")
def get_trade_history():
    return {"history": trade_history}

@app.get("/api/open-position")
def get_open_position():
    return {"position": open_position}

def auto_refresh():
    while True:
        if auto_refresh_enabled:
            try:
                for ticker in list(latest_signal.keys()):
                    data = yf.download(ticker, period="5d", interval="15m")
                    if not data.empty:
                        data = calculate_indicators(data)
                        latest_signal[ticker] = generate_signals(data, "Scalping")
            except:
                pass
        time.sleep(60)

threading.Thread(target=auto_refresh, daemon=True).start()
