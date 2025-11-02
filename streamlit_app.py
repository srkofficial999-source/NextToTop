import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import yfinance as yf
import ta
import datetime
import requests

# ================= CONFIG =================
st.set_page_config(page_title="AI Intraday NSE Dashboard", layout="wide")

WATCHLIST = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "ICICIBANK.NS"]
REFRESH_SEC = 60  # Auto refresh every 60 seconds

# --- Read Telegram credentials from secrets (safe for cloud) ---
TELEGRAM_BOT_TOKEN = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")

# ==========================================

# -------- TELEGRAM FUNCTION ---------------
def send_telegram(msg):
    """Send message to Telegram if secrets are set."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except Exception as e:
        print("Telegram error:", e)

# -------- INDICATOR FUNCTION ---------------
def indicators(df):
    df["ema8"] = ta.trend.EMAIndicator(df["Close"], window=8).ema_indicator()
    df["ema21"] = ta.trend.EMAIndicator(df["Close"], window=21).ema_indicator()
    df["rsi14"] = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
    macd = ta.trend.MACD(df["Close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    return df

# -------- SIGNAL FUNCTION -----------------
def generate_signal(df):
    last = df.iloc[-1]
    if last["ema8"] > last["ema21"] and last["macd"] > last["macd_signal"] and last["rsi14"] < 70:
        return "BUY"
    elif last["ema8"] < last["ema21"] and last["macd"] < last["macd_signal"] and last["rsi14"] > 30:
        return "SELL"
    else:
        return "HOLD"

# -------- AFTER MARKET ANALYSIS -----------
def after_market_analysis(watch):
    analysis_rows = []
    for sym in watch:
        try:
            df = yf.download(tickers=sym, period="10d", interval="1d", progress=False)
            if df.empty:
                continue
            df = indicators(df)
            last = df.iloc[-1]
            if last["ema8"] > last["ema21"] and last["rsi14"] > 55:
                bias = "📈 Buy Side"
            elif last["ema8"] < last["ema21"] and last["rsi14"] < 45:
                bias = "🔻 Sell Side"
            else:
                bias = "⚪ Neutral"
            analysis_rows.append({
                "Symbol": sym.replace(".NS", ""),
                "EMA Trend": "Above" if last["ema8"] > last["ema21"] else "Below",
                "RSI": round(last["rsi14"], 1),
                "Tomorrow Bias": bias
            })
        except Exception as e:
            print(f"{sym} analysis error:", e)
    return pd.DataFrame(analysis_rows)

# -------- HEADER --------------------------
st.title("📊 AI Intraday Trading Dashboard — NSE India")
st.caption("Powered by Streamlit + yFinance + Technical Indicators")

# Auto-refresh every REFRESH_SEC seconds
count = st_autorefresh(interval=REFRESH_SEC * 1000, limit=None, key="autorefresh")

# -------- SESSION STATE for alerts --------
if "last_signals" not in st.session_state:
    st.session_state["last_signals"] = {}

# -------- LIVE ANALYSIS -------------------
live_rows = []
indicator_rows = []

for sym in WATCHLIST:
    try:
        df = yf.download(tickers=sym, period="5d", interval="5m", progress=False)
        if df.empty:
            continue
        df = indicators(df)
        sig = generate_signal(df)
        last = df.iloc[-1]

        ema_buy = (last["ema8"] > last["ema21"])
        macd_buy = (last["macd"] > last["macd_signal"])
        rsi_val = last["rsi14"]

        indicator_rows.append({
            "Symbol": sym.replace(".NS", ""),
            "EMA": "✅ Buy" if ema_buy else "🔻 Sell",
            "MACD": "✅ Bullish" if macd_buy else "🔻 Bearish",
            "RSI": f"{rsi_val:.1f}" + (" ✅ OK" if 30 < rsi_val < 70 else " ⚠️ Extreme"),
            "Signal": sig
        })

        live_rows.append({
            "Symbol": sym.replace(".NS", ""),
            "Last Price": round(last["Close"], 2),
            "RSI": round(rsi_val, 2),
            "Signal": sig,
            "Time": datetime.datetime.now().strftime("%H:%M:%S")
        })

        # --- Send Telegram alert only when signal changes ---
        prev_signal = st.session_state["last_signals"].get(sym)
        if sig in ["BUY", "SELL"] and sig != prev_signal:
            send_telegram(f"🚨 {sym}: {sig} Signal triggered (RSI={rsi_val:.1f})")
            st.session_state["last_signals"][sym] = sig

    except Exception as e:
        print(f"{sym} fetch error:", e)

# -------- DISPLAY SECTIONS ----------------
st.subheader("📈 Live Intraday Signals")
if live_rows:
    st.dataframe(pd.DataFrame(live_rows), use_container_width=True)
else:
    st.warning("No data fetched. Try again later.")

st.subheader("📊 Indicator Status (RSI, EMA, MACD)")
st.dataframe(pd.DataFrame(indicator_rows), use_container_width=True)

st.subheader("📅 After Market Analysis (Tomorrow Setup)")
st.dataframe(after_market_analysis(WATCHLIST), use_container_width=True)

st.caption(f"⏱ Auto-refreshing every {REFRESH_SEC} sec | Last updated: {datetime.datetime.now().strftime('%H:%M:%S')}")