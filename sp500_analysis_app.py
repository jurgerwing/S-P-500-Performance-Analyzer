# Integrated S&P 500 and CSI 300 Analyzer (No News)

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# --- Page Config ---
st.set_page_config(layout="wide", page_title="Market Analyzer (S&P 500 & CSI 300)")

# --- Load CSI 300 Metadata ---
@st.cache_data
def load_csi300_metadata():
    xlsx = pd.ExcelFile("CSI 300.xlsx")  # Replace with full path if necessary
    df = xlsx.parse("Sheet1")

    def convert_to_yahoo_format(ticker):
        code = ticker.split()[0]
        if code.startswith('6'):
            return f"{code}.SS"
        elif code.startswith(('0', '3')):
            return f"{code}.SZ"
        else:
            return None

    df['Yahoo Ticker'] = df['Ticker'].apply(convert_to_yahoo_format)
    df = df[['Yahoo Ticker', 'Company', 'Sector', 'Industry Group']].dropna()
    df = df.rename(columns={
        'Yahoo Ticker': 'Ticker',
        'Industry Group': 'Industry'
    }).reset_index(drop=True)
    return df

# --- Load S&P 500 Metadata ---
@st.cache_data
def get_sp500_metadata():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    df = df.rename(columns={
        'Symbol': 'Ticker',
        'Security': 'Company',
        'GICS Sector': 'Sector',
        'GICS Sub-Industry': 'Industry'
    })
    return df[['Ticker', 'Company', 'Sector', 'Industry']]

# --- Price Data Fetcher ---
@st.cache_data
def get_price_data(tickers, start_date, end_date):
    start_buffer = (pd.to_datetime(start_date) - timedelta(days=5)).strftime('%Y-%m-%d')
    end_buffer = (pd.to_datetime(end_date) + timedelta(days=1)).strftime('%Y-%m-%d')
    data = yf.download(tickers, start=start_buffer, end=end_buffer, group_by="ticker", auto_adjust=True, threads=True)

    price_data = {}
    for ticker in tickers:
        try:
            df = data[ticker][['Close']].copy()
            df['Daily % Change'] = df['Close'].pct_change() * 100
            df.dropna(inplace=True)
            df = df.loc[(df.index.date >= pd.to_datetime(start_date).date()) & 
                        (df.index.date <= pd.to_datetime(end_date).date())]
            price_data[ticker] = df
        except Exception:
            continue
    return price_data

# --- Performance Calculation ---
def compute_performance(price_data):
    return {ticker: df['Daily % Change'].sum() for ticker, df in price_data.items()}

# --- Display Functions ---
def display_top_movers(performance, metadata, title, ascending=False):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df = df.merge(metadata, on='Ticker', how='left')
    df = df[['Ticker', 'Company', 'Return']].sort_values(by='Return', ascending=ascending).reset_index(drop=True)
    df.index += 1
    st.subheader(title)
    st.dataframe(df.head(10).style.format({'Return': '{:.2f}%'}), use_container_width=True)

def display_group_performance(performance, metadata, group_col, title):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df = df.merge(metadata, on='Ticker', how='left')
    group_perf = df.groupby(group_col)['Return'].mean().sort_values(ascending=False).round(2)
    group_df = group_perf.reset_index().rename(columns={'Return': 'Avg Return (%)'})
    group_df.index += 1
    st.subheader(title)
    st.dataframe(group_df, use_container_width=True)

# --- UI: Index Toggle ---
st.sidebar.title("📊 Index Selector")
index_choice = st.sidebar.selectbox("Select Index:", ["S&P 500", "CSI 300"])

# --- UI: Date Selector ---
today = datetime.today().date()
def_start = datetime(today.year, 1, 1).date()
start_date = st.sidebar.date_input("Start Date", def_start)
end_date = st.sidebar.date_input("End Date", today)
if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

# --- Load Metadata ---
with st.spinner("Loading metadata..."):
    metadata = get_sp500_metadata() if index_choice == "S&P 500" else load_csi300_metadata()
    tickers = metadata['Ticker'].tolist()

# --- Fetch Price Data ---
with st.spinner("Fetching live market data..."):
    price_data = get_price_data(tickers, start_date, end_date)

if not price_data:
    st.error("⚠️ No valid data returned. Try a different date range or check internet connection.")
    st.stop()

performance = compute_performance(price_data)

# --- Display ---
st.title(f"📈 {index_choice} Performance Analyzer")
st.markdown(f"**Date Range:** {start_date} to {end_date}")

col1, col2 = st.columns(2)
with col1:
    display_top_movers(performance, metadata, "🔼 Top 10 Gainers", ascending=False)
with col2:
    display_top_movers(performance, metadata, "🔽 Top 10 Losers", ascending=True)

display_group_performance(performance, metadata, "Sector", "📊 Sector Performance")
display_group_performance(performance, metadata, "Industry", "📊 Industry Group Performance")

# --- Ticker Inspector ---
st.sidebar.markdown("---")
selected_ticker = st.sidebar.selectbox("🔍 Inspect Specific Ticker", ["None"] + sorted(price_data.keys()))
if selected_ticker != "None":
    st.subheader(f"Daily % Changes for {selected_ticker}")
    df = price_data[selected_ticker].copy()
    df['Cumulative % Change'] = df['Daily % Change'].cumsum()
    st.line_chart(df['Cumulative % Change'])
    st.dataframe(df.round(2), use_container_width=True)

# --- Footer ---
latest_date = max([df.index.max() for df in price_data.values()])
st.markdown(f"---\n_Last updated: **{latest_date.date()}**_", unsafe_allow_html=True)
