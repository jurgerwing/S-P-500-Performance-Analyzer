import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Index Performance Analyzer")

# --- S&P 500 Metadata Loader ---
@st.cache_data
def get_sp500_metadata():
    try:
        df = pd.read_csv("S&P 500.csv")
        df.columns = [col.strip() for col in df.columns]
        col_map = {}
       for c in df.columns:
        cl = str(c).lower()
        if "security" in cl or "company" in cl or "name" in cl: col_map[c] = "Security"
        elif "sector" in cl: col_map[c] = "GICS Sector"
        elif "industry group" in cl: col_map[c] = "GICS Sub-Industry"
        elif "industry" in cl: col_map[c] = "GICS Sub-Industry"
        df.rename(columns=col_map, inplace=True)
        # Check columns
        required_cols = ["Symbol", "Security"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"S&P 500 CSV missing '{col}' column after mapping.")
                return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"S&P 500 CSV error: {e}")
        return pd.DataFrame()

# --- CSI 300 Metadata Loader ---
@st.cache_data
def load_csi300_metadata():
    try:
        df = pd.read_excel("CSI 300.xlsx")
        possible_names = ["Ticker", "代码", "Code", "Symbol", "Stock Code"]
        ticker_col = next((c for c in df.columns if any(x.lower() in c.lower() for x in possible_names)), None)
        if not ticker_col:
            st.error(f"CSI 300: No ticker column found. Columns: {df.columns.tolist()}")
            return pd.DataFrame()
        df["Cleaned"] = df[ticker_col].astype(str).str.extract(r"(\d{6})")
        df = df.dropna(subset=["Cleaned"])
        def fix_ticker(ticker):
            if ticker.startswith("6"): return ticker + ".SS"
            elif ticker.startswith("0") or ticker.startswith("3"): return ticker + ".SZ"
            else: return None
        df["Symbol"] = df["Cleaned"].apply(fix_ticker)
        df = df.dropna(subset=["Symbol"])
        col_map = {}
        for c in df.columns:
            cl = str(c).lower()
            if "security" in cl or "company" in cl or "name" in cl: col_map[c] = "Security"
            elif "sector" in cl: col_map[c] = "GICS Sector"
            elif "industry group" in cl: col_map[c] = "GICS Sub-Industry"
            elif "industry" in cl: col_map[c] = "GICS Sub-Industry"
        df.rename(columns=col_map, inplace=True)
        # Check columns
        required_cols = ["Symbol", "Security"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"CSI 300 Excel missing '{col}' column after mapping.")
                return pd.DataFrame()
        return df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]
    except Exception as e:
        st.error(f"CSI 300 Excel error: {e}")
        return pd.DataFrame()

# --- Price download per ticker (bulletproof) ---
@st.cache_data
def get_price_data(tickers, start_date, end_date):
    price_data = {}
    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date - timedelta(days=5), end=end_date + timedelta(days=1), auto_adjust=True, progress=False)
            if data.empty or 'Close' not in data.columns: continue
            df = data[['Close', 'Volume']].copy()
            df['Daily % Change'] = df['Close'].pct_change() * 100
            df = df[(df.index.date >= start_date) & (df.index.date <= end_date)]
            df.dropna(inplace=True)
            price_data[ticker] = df
        except Exception:
            continue
    return price_data

def compute_performance(price_data):
    perf = {}
    avg_volume = {}
    for ticker, df in price_data.items():
        perf[ticker] = df['Daily % Change'].sum()
        avg_volume[ticker] = df['Volume'].mean() if 'Volume' in df else float('nan')
    return perf, avg_volume

def display_top_movers(performance, avg_volume, metadata, title, ascending=False):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df['Avg Volume'] = df['Ticker'].map(avg_volume)
    df = df.merge(metadata, left_on='Ticker', right_on='Symbol', how='left')
    df = df[['Ticker', 'Security', 'Return', 'Avg Volume']].sort_values(by='Return', ascending=ascending).head(10)
    df.reset_index(drop=True, inplace=True)
    df.index += 1
    # ---- Robust: ensure correct dtypes before styling
    df['Return'] = pd.to_numeric(df['Return'], errors='coerce')
    df['Avg Volume'] = pd.to_numeric(df['Avg Volume'], errors='coerce')
    st.subheader(title)
    st.dataframe(df.style.format({'Return': '{:.2f}%', 'Avg Volume': '{:,.0f}'}), use_container_width=True)

def display_group_performance(performance, avg_volume, metadata, group_col, title):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df['Avg Volume'] = df['Ticker'].map(avg_volume)
    df = df.merge(metadata, left_on='Ticker', right_on='Symbol', how='left')
    # Force columns to numeric before groupby!
    df['Return'] = pd.to_numeric(df['Return'], errors='coerce')
    df['Avg Volume'] = pd.to_numeric(df['Avg Volume'], errors='coerce')
    # Defensive: check if group_col is present
    if group_col not in df.columns:
        st.warning(f"Column '{group_col}' not present in metadata for group performance.")
        return
    group_perf = df.groupby(group_col).agg({
        'Return': 'mean',
        'Avg Volume': 'mean'
    }).sort_values(by='Return', ascending=False).round(2).reset_index()
    group_perf.rename(columns={'Return': 'Avg Return (%)', 'Avg Volume': 'Avg Volume'}, inplace=True)
    group_perf.index += 1
    st.subheader(title)
    st.dataframe(group_perf, use_container_width=True)

# --- Sidebar controls ---
st.sidebar.title("Index Selector")
index_choice = st.sidebar.selectbox("Choose Index", ["S&P 500", "CSI 300"])

st.sidebar.markdown("---")
today = datetime.today().date()
default_start = datetime(today.year, 1, 1).date()
start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", today, max_value=today)
if start_date > end_date:
    st.error("⚠️ Start date must be before end date.")
    st.stop()

# --- Load metadata & tickers ---
metadata = get_sp500_metadata() if index_choice == "S&P 500" else load_csi300_metadata()
if metadata.empty:
    st.error(f"{index_choice} metadata not loaded. Please check your CSV/XLSX and restart the app.")
    st.stop()
tickers = metadata['Symbol'].dropna().unique().tolist()
if not tickers:
    st.error("No valid tickers found in metadata.")
    st.stop()

# --- Download prices (robust and slow but sure) ---
with st.spinner("Downloading price data..."):
    price_data = get_price_data(tickers, start_date, end_date)

if not price_data:
    st.error("⚠️ No valid data returned. Try a wider or different date range.")
    st.stop()

performance, avg_volume = compute_performance(price_data)

# --- UI ---
st.title(f"{index_choice} Performance Analyzer")
st.markdown(f"**Date Range:** `{start_date}` to `{end_date}`")
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["🏆 Top Movers", "📊 Group Performance", "🔍 Ticker Inspector"])
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        display_top_movers(performance, avg_volume, metadata, "Top 10 Gainers", ascending=False)
    with col2:
        display_top_movers(performance, avg_volume, metadata, "Top 10 Losers", ascending=True)
with tab2:
    display_group_performance(performance, avg_volume, metadata, "GICS Sector", "Sector Performance")
    st.markdown("___")
    display_group_performance(performance, avg_volume, metadata, "GICS Sub-Industry", "Industry Group Performance")
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
if price_data:
    try:
        latest_date = max(df.index.max() for df in price_data.values())
        st.markdown("---")
        st.caption(f"Data provided by yfinance • Last updated: {latest_date.strftime('%Y-%m-%d')}")
    except Exception:
        st.markdown("---")
        st.caption("Data provided by yfinance • Last updated: Unknown")
