import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Index Performance Analyzer")

# --- Robust S&P 500 metadata loader ---
@st.cache_data
def get_sp500_metadata():
    # Try all common filename permutations
    for filename in ["S&P 500.csv", "S&P500.csv", "s&p 500.csv", "sp500.csv"]:
        try:
            df = pd.read_csv(filename)
            break
        except FileNotFoundError:
            continue
    else:
        st.error("S&P 500 metadata CSV not found. Please check the filename and upload location.")
        return pd.DataFrame()
    
    # Clean and normalize columns
    df.columns = [c.strip().replace("\ufeff", "") for c in df.columns]
    cols_lower = [c.lower() for c in df.columns]
    col_map = {}
    # Dynamically map known names to standardized ones
    for c in df.columns:
        cl = c.lower()
        if "symbol" in cl: col_map[c] = "Symbol"
        elif "security" in cl or "company" in cl: col_map[c] = "Security"
        elif "sector" in cl: col_map[c] = "GICS Sector"
        elif "industry group" in cl: col_map[c] = "GICS Industry"
        elif "sub-industry" in cl: col_map[c] = "GICS Sub-Industry"
    df.rename(columns=col_map, inplace=True)
    # Confirm essential columns
    for col in ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]:
        if col not in df.columns:
            st.error(f"Column '{col}' not found in your S&P 500 CSV (columns: {df.columns.tolist()})")
            return pd.DataFrame()
    df = df.drop_duplicates(subset=["Symbol"])
    return df

# --- Robust CSI 300 metadata loader ---
@st.cache_data
def load_csi300_metadata():
    try:
        df = pd.read_excel("CSI 300.xlsx")
    except FileNotFoundError:
        st.error("CSI 300 metadata Excel file not found.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading CSI 300 metadata: {e}")
        return pd.DataFrame()

    # Show user the columns if there's a loading error
    st.write("CSI 300 columns:", df.columns.tolist())

    # Try all reasonable ticker column names
    possible_names = ["Ticker", "代码", "Code", "Symbol", "Stock Code"]
    ticker_col = next((c for c in df.columns if any(x.lower() in c.lower() for x in possible_names)), None)
    if not ticker_col:
        st.error(f"No column for ticker found! Headers: {df.columns.tolist()}")
        return pd.DataFrame()
    
    df["Cleaned"] = df[ticker_col].astype(str).str.extract(r"(\d{6})")
    df = df.dropna(subset=["Cleaned"])
    def fix_ticker(ticker):
        if ticker.startswith("6"): return ticker + ".SS"
        elif ticker.startswith("0") or ticker.startswith("3"): return ticker + ".SZ"
        else: return None
    df["Symbol"] = df["Cleaned"].apply(fix_ticker)
    df = df.dropna(subset=["Symbol"])

    # Flexible mapping for security/sector/industry
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "security" in cl or "company" in cl or "name" in cl: col_map[c] = "Security"
        elif "sector" in cl: col_map[c] = "GICS Sector"
        elif "industry" in cl: col_map[c] = "GICS Sub-Industry"
        elif "industry group" in cl: col_map[c] = "GICS Sub-Industry"
    df.rename(columns=col_map, inplace=True)
    for col in ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]:
        if col not in df.columns:
            st.error(f"Column '{col}' not found in your CSI 300 file (columns: {df.columns.tolist()})")
            return pd.DataFrame()
    return df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]

# --- Price download ---
@st.cache_data(show_spinner="Downloading price data…")
def get_price_data(tickers, start_date, end_date):
    start_buffer = (pd.to_datetime(start_date) - timedelta(days=5)).strftime('%Y-%m-%d')
    end_buffer = (pd.to_datetime(end_date) + timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        data = yf.download(tickers, start=start_buffer, end=end_buffer, group_by="ticker", auto_adjust=True, threads=True)
    except Exception as e:
        st.error(f"Yahoo download error: {e}")
        return {}
    price_data = {}
    for ticker in tickers:
        try:
            # yfinance returns DataFrame for each ticker if multiple, Series if only one
            tdata = data[ticker] if ticker in data else None
            if tdata is None or tdata.empty: continue
            if isinstance(tdata, pd.Series): tdata = tdata.to_frame().T
            if "Close" not in tdata.columns: continue
            tdata = tdata[['Close', 'Volume']].copy()
            tdata['Daily % Change'] = tdata['Close'].pct_change() * 100
            tdata = tdata.dropna()
            tdata = tdata.loc[(tdata.index.date >= pd.to_datetime(start_date).date()) &
                              (tdata.index.date <= pd.to_datetime(end_date).date())]
            if len(tdata) > 0:
                price_data[ticker] = tdata
        except Exception:
            continue
    return price_data

# --- Helpers ---
def compute_performance(price_data):
    perf, avg_volume = {}, {}
    for ticker, df in price_data.items():
        perf[ticker] = df['Daily % Change'].sum()
        avg_volume[ticker] = df['Volume'].mean()
    return perf, avg_volume

def highlight_returns(val):
    color = 'green' if val > 0 else 'red'
    return f'color: {color}; font-weight: bold'

def display_top_movers(performance, avg_volume, metadata, title, ascending=False):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df['Avg Volume'] = df['Ticker'].map(avg_volume)
    df = df.merge(metadata, left_on='Ticker', right_on='Symbol', how='left')
    df = df[['Ticker', 'Security', 'Return', 'Avg Volume']].sort_values(by='Return', ascending=ascending).head(10)
    df.index = range(1, len(df)+1)
    styled_df = df.style.format({'Return': '{:.2f}%', 'Avg Volume': '{:,.0f}'}).applymap(highlight_returns, subset=['Return'])
    st.subheader(title)
    st.dataframe(styled_df, use_container_width=True)

def display_group_performance(performance, avg_volume, metadata, group_col, title):
    df = pd.DataFrame(performance.items(), columns=['Ticker', 'Return'])
    df['Avg Volume'] = df['Ticker'].map(avg_volume)
    df = df.merge(metadata, left_on='Ticker', right_on='Symbol', how='left')
    if group_col not in df.columns:
        st.warning(f"Grouping column `{group_col}` not found in data (columns: {df.columns.tolist()})")
        return
    group_perf = df.groupby(group_col).agg({'Return': 'mean', 'Avg Volume': 'mean'}).sort_values(by='Return', ascending=False).round(2).reset_index()
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

# --- Load metadata & price ---
metadata = get_sp500_metadata() if index_choice == "S&P 500" else load_csi300_metadata()
if metadata.empty:
    st.error("No metadata loaded — check file and columns.")
    st.stop()
tickers = metadata['Symbol'].dropna().unique().tolist()

with st.spinner("Downloading price data..."):
    price_data = get_price_data(tickers, start_date, end_date)

if not price_data:
    st.error("⚠️ No valid data returned. Try a wider or different date range.")
    st.stop()

performance, avg_volume = compute_performance(price_data)

# --- Title ---
st.title(f"{index_choice} Performance Analyzer")
st.markdown(f"**Date Range:** `{start_date}` to `{end_date}`")
st.markdown("---")

# --- Tabs ---
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

# --- Footer ---
if price_data:
    try:
        latest_date = max(df.index.max() for df in price_data.values())
        latest_date_str = latest_date.strftime("%Y-%m-%d")
        st.markdown("---")
        st.caption(f"Data provided by yfinance • Last updated: {latest_date_str}")
    except Exception:
        st.markdown("---")
        st.caption("Data provided by yfinance • Last updated: Unknown")
