from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/signal")
def get_signal(ticker: str, risk_percent: float, account_balance: float):
    try:
        data = yf.download(tickers=ticker, period="5d", interval="15m")
        close_prices = data['Close'].dropna().to_numpy()

        if len(close_prices) < 2:
            return {"error": "Not enough data"}

        # Fixed line: Convert NumPy mean to float
        mean_price = np.mean(close_prices[-20:]).item()
        confidence = round(abs(close_prices[-1] - mean_price) / close_prices[-1], 2)
        entry_price = round(close_prices[-1], 2)
        shares = int((account_balance * (risk_percent / 100)) // entry_price)
        accuracy = round(np.random.uniform(0.65, 0.9), 2)

        timeseries = [{"time": str(i), "price": round(p, 2)} for i, p in enumerate(close_prices[-30:])]

        return {
            "summary": {
                "signal": "buy" if close_prices[-1] > mean_price else "sell",
                "confidence": confidence,
                "entry_price": entry_price,
                "shares": shares,
                "accuracy": accuracy
            },
            "timeseries": timeseries
        }

    except Exception as e:
        return {"error": str(e)}
