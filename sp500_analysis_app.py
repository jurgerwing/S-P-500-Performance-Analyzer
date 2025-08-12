import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser

@st.cache_data
def get_live_rss_headlines():
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:10]]

st.set_page_config(layout="wide", page_title="S&P 500 Analyzer")

@st.cache_data
def get_sp500_tickers():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    return df[['Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry']]

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

def compute_performance(price_data):
    return {ticker: df['Daily % Change'].sum() for ticker, df in price_data.items()}

def highlight_returns(val):
    color = 'green' if val > 0 else 'red'
    return f'color: {color}; font-weight: bold'

def display_top_movers(performance, metadata, title, ascending=False):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df = df.merge(metadata, left_on='Ticker', right_on='Symbol', how='left')
    df = df[['Ticker', 'Security', 'Return']].sort_values(by='Return', ascending=ascending).head(10)
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    styled_df = df.style.format({'Return': '{:.2f}%'}).applymap(highlight_returns, subset=['Return'])
    st.subheader(title)
    st.dataframe(styled_df, use_container_width=True)

def display_group_performance(performance, metadata, group_col, title):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df = df.merge(metadata, left_on='Ticker', right_on='Symbol', how='left')
    group_perf = df.groupby(group_col)['Return'].mean().sort_values(ascending=False).round(2)
    group_perf = group_perf.reset_index().rename(columns={'Return': 'Avg Return (%)'})
    group_perf.index = group_perf.index + 1 
    st.subheader(title)
    st.dataframe(group_perf, use_container_width=True)

# --- Sidebar ---
st.sidebar.header("Controls & Filters")
today = datetime.today().date()
default_start = datetime(today.year, 1, 1).date()

start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", today, max_value=today)

if start_date > end_date:
    st.error("⚠️ Start date must be before end date.")
    st.stop()

# --- Load data ---
metadata = get_sp500_tickers()
tickers = metadata['Symbol'].tolist()

with st.spinner("Fetching price data..."):
    price_data = get_price_data(tickers, start_date, end_date)

if not price_data:
    st.error("⚠️ No valid data returned. Try a wider or different date range.")
    st.stop()

performance = compute_performance(price_data)

# --- Get latest date for footer ---
latest_date = max(df.index.max() for df in price_data.values())
latest_date_str = latest_date.strftime("%Y-%m-%d")

# --- Title ---
st.title("S&P 500 Performance Analyzer")
st.markdown(f"**Date Range:** `{start_date}` to `{end_date}`")
st.markdown("---")

# --- Tabs Layout ---
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Top Movers", "📊 Group Performance", "🔍 Ticker Inspector", "🗞️ Live Headlines"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        display_top_movers(performance, metadata, "Top 10 Gainers", ascending=False)
    with col2:
        display_top_movers(performance, metadata, "Top 10 Losers", ascending=True)

with tab2:
    display_group_performance(performance, metadata, "GICS Sector", "Sector Performance")
    st.markdown("___")
    display_group_performance(performance, metadata, "GICS Sub-Industry", "Industry Group Performance")

with tab3:
    st.sidebar.markdown("---")
    selected_ticker = st.sidebar.selectbox("Inspect Specific Ticker", ["None"] + sorted(price_data.keys()))
if selected_ticker != "None":
    st.subheader(f"Cumulative % Return for `{selected_ticker}`")
    df = price_data[selected_ticker].copy().round(2)
    df['Cumulative % Change'] = df['Daily % Change'].cumsum()
    total_return = df['Daily % Change'].sum()

    st.line_chart(df['Cumulative % Change'])
    st.dataframe(df, use_container_width=True)
    st.markdown(f"**Total Movement:** `{total_return:.2f}%`")

with tab4:
    st.subheader("🗞️ Live Market Headlines")

    with st.spinner("Loading headlines..."):
        headlines = get_live_rss_headlines()

    if headlines:
        for hl in headlines:
            st.markdown(f"- {hl}")
    else:
        st.info("No headlines available at this time.")

    st.caption("These headlines are fetched live and do not reflect the selected date range.")

# --- Footer ---
latest_date = max(df.index.max() for df in price_data.values())
latest_date_str = latest_date.strftime("%Y-%m-%d")

st.markdown("---")
st.caption(f"Data provided by yfinance • Headlines provided by rss feeds • Last updated: {latest_date_str}")
