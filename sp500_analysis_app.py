import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date

# --- Helper functions for both indices ---
@st.cache_data(show_spinner=False)
def get_sp500_metadata():
    return yf.Tickers(" ".join(sp500_tickers)).tickers

@st.cache_data(show_spinner=False)
def get_csi300_metadata():
    df = pd.read_excel("CSI 300.xlsx")
    df["Symbol"] = df["Ticker"].astype(str).str.strip().apply(
        lambda t: f"{t}.SS" if t.startswith("6") else f"{t}.SZ" if t.startswith(("0", "3")) else None
    )
    df.dropna(subset=["Symbol"], inplace=True)
    return df[["Symbol", "Company", "Sector", "Industry Group"]].rename(columns={"Symbol": "Ticker"})

@st.cache_data(show_spinner=False)
def download_data(tickers, start_date, end_date):
    return yf.download(tickers, start=start_date, end=end_date, group_by="ticker", auto_adjust=True, progress=False)

def calculate_performance(data):
    performance = {}
    for ticker in data.columns.levels[0]:
        close_prices = data[ticker]["Close"]
        pct_change = close_prices.pct_change().dropna() * 100
        performance[ticker] = pct_change.sum()
    return pd.Series(performance).sort_values(ascending=False)

def display_top_movers(performance, metadata, title, ascending):
    df = performance.sort_values(ascending=ascending).head(10).reset_index()
    df.columns = ["Ticker", "Performance"]
    df = df.merge(metadata, on="Ticker", how="left")
    st.subheader(title)
    st.dataframe(df[["Ticker", "Company", "Performance", "Sector", "Industry Group"]])

# --- Streamlit UI Setup ---
st.set_page_config(layout="wide", page_title="Market Performance Dashboard")
st.markdown("""
    <style>
        html, body, [class*="css"]  {
            font-family: 'Helvetica Neue', sans-serif;
        }
        .block-container {
            padding-top: 2rem;
        }
        footer { visibility: hidden; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 S&P 500 & CSI 300 Performance Analyzer")
st.caption("Live performance metrics using Yahoo Finance data")

# --- Select Index ---
index_choice = st.radio("Select Index", ["S&P 500", "CSI 300"], horizontal=True)

# --- Select Date Range ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", date(2025, 1, 1))
with col2:
    end_date = st.date_input("End Date", date.today())

if index_choice == "S&P 500":
    from yfinance import tickers_sp500
    sp500_tickers = tickers_sp500()
    metadata = pd.DataFrame({"Ticker": sp500_tickers})
    data = download_data(sp500_tickers, start_date, end_date)
    performance = calculate_performance(data)
    display_top_movers(performance, metadata, "Top 10 Gainers", ascending=False)
    display_top_movers(performance, metadata, "Top 10 Losers", ascending=True)

else:
    metadata = get_csi300_metadata()
    tickers = metadata["Ticker"].tolist()
    data = download_data(tickers, start_date, end_date)
    performance = calculate_performance(data)
    display_top_movers(performance, metadata, "Top 10 Gainers", ascending=False)
    display_top_movers(performance, metadata, "Top 10 Losers", ascending=True)

# --- Footer ---
st.markdown("<center style='font-size: 0.9em; color: gray;'>Powered by yfinance • Streamlit App by Jacob</center>", unsafe_allow_html=True)
