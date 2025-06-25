from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from typing import Optional
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_preferences = {}
trade_log = []

@app.get("/api/set-preference")
def set_preference(key: str, value: str):
    user_preferences[key] = value.lower() == "true"
    return {"status": "updated", "preferences": user_preferences}

@app.get("/api/signal")
def get_signal(ticker: str, strategy: str = "Swing Trading"):
    data = yf.download(ticker, period="5d", interval="15m")
    data.dropna(inplace=True)

    data['EMA20'] = data['Close'].ewm(span=20).mean()
    data['EMA50'] = data['Close'].ewm(span=50).mean()
    data['RSI'] = 100 - (100 / (1 + data['Close'].pct_change().rolling(window=14).mean()))
    data['MACD'] = data['EMA20'] - data['EMA50']

    latest = data.iloc[-1]
    signal = "BUY" if latest['MACD'].item() > 0 and latest['RSI'].item() < 70 else "SELL"
    confidence = 85 if signal == "BUY" else 70
    entry_price = round(latest['Close'], 2)
    stop = round(entry_price * 0.98, 2)
    take = round(entry_price * 1.02, 2)
    support = round(data['Low'].rolling(window=20).min().iloc[-1], 2)
    resistance = round(data['High'].rolling(window=20).max().iloc[-1], 2)

    gaps = []
    close_std = data['Close'].std()
    for i in range(1, len(data)):
        open_now = data['Open'].iloc[i]
        close_prev = data['Close'].iloc[i - 1]
        gap_threshold = close_std
        if abs(open_now - close_prev) > gap_threshold:
            gaps.append({
                "time": data.index[i].strftime('%Y-%m-%d %H:%M'),
                "price": open_now,
                "type": "gap"
            })

    trade = {
        "signal": signal,
        "entry": entry_price,
        "confidence": confidence,
        "sentiment": "Bullish" if signal == "BUY" else "Bearish",
        "stop": stop,
        "take": take,
        "support": support,
        "resistance": resistance,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "reason": f"MACD: {round(latest['MACD'], 2)}, RSI: {round(latest['RSI'], 2)}",
        "gaps": gaps,
        "PnL_dollars": 0,
        "PnL_percent": 0
    }

    trade_log.append(trade)
    if len(trade_log) > 100:
        trade_log.pop(0)

    return trade

@app.get("/api/trades")
def get_trade_history():
    return {"history": trade_log}

@app.get("/api/chart", response_class=HTMLResponse)
def get_chart(ticker: str, theme: str = "dark", showVolume: bool = True, candleStyle: str = "candlestick"):
    df = yf.download(ticker, period="5d", interval="15m")
    if df.empty:
        return HTMLResponse("<div style='color:white;padding:1em;'>No chart data available.</div>")

    fig = go.Figure()

    if candleStyle == "candlestick":
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="Candles"
        ))
    elif candleStyle == "ohlc":
        fig.add_trace(go.Ohlc(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="OHLC"
        ))
    elif candleStyle == "line":
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['Close'],
            mode='lines',
            name="Line Chart"
        ))

    if showVolume:
        fig.add_trace(go.Bar(
            x=df.index,
            y=df['Volume'],
            name="Volume",
            yaxis="y2"
        ))

    fig.update_layout(
        template="plotly_dark" if theme == "dark" else "plotly_white",
        margin=dict(t=20, b=20),
        height=500,
        yaxis=dict(title="Price"),
        yaxis2=dict(
            title="Volume",
            overlaying="y",
            side="right",
            showgrid=False
        )
    )

    return HTMLResponse(content=fig.to_html(include_plotlyjs='cdn'))

            showgrid=False
        )
    )

    return HTMLResponse(content=fig.to_html(include_plotlyjs='cdn'))
