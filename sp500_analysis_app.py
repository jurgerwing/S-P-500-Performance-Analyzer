# CSI 300 + S&P 500 Analyzer with Consistent Trading Dates and Timezones

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from io import BytesIO

@st.cache_data

def load_csi300_metadata():
    # Load tickers from uploaded Excel file
    xlsx = pd.ExcelFile("CSI 300.xlsx")
    df = xlsx.parse(xlsx.sheet_names[0])
    df = df[['Ticker', 'Company Name', 'Sector', 'Industry']].dropna()
    df['Ticker'] = df['Ticker'].astype(str).str.zfill(6)
    df['Yahoo Ticker'] = df['Ticker'].apply(lambda x: x + '.SS' if x.startswith('6') else x + '.SZ')
    return df

@st.cache_data

def get_sp500_metadata():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    table = table[['Symbol', 'Security', 'GICS Sector', 'GICS Sub-Industry']]
    table.columns = ['Ticker', 'Company Name', 'Sector', 'Industry']
    return table

def get_trading_days(tickers, start_date, end_date):
    # Pick a valid ticker to get trading days (e.g., AAPL or 000001.SZ)
    data = yf.download(tickers[0], start=start_date, end=end_date, auto_adjust=False, progress=False)
    return data.index.normalize()

def get_performance(df, start_date, end_date):
    tickers = df['Yahoo Ticker'].tolist() if 'Yahoo Ticker' in df.columns else df['Ticker'].tolist()
    perf = []

    valid_days = get_trading_days(tickers, start_date, end_date)

    for i, ticker in enumerate(tickers):
        try:
            data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, progress=False)
            if data.empty:
                continue
            data = data.loc[valid_days.intersection(data.index)]
            data['Pct Change'] = data['Close'].pct_change() * 100
            total = data['Pct Change'].dropna().sum()
            perf.append((ticker, total))
        except:
            continue

    perf_df = pd.DataFrame(perf, columns=['Ticker', 'Performance'])
    merged = df.merge(perf_df, on='Ticker' if 'Yahoo Ticker' not in df.columns else 'Yahoo Ticker')
    return merged.sort_values(by='Performance', ascending=False)

# --------------------- Streamlit UI ---------------------
st.set_page_config(layout="wide")
st.title("📈 S&P 500 + CSI 300 Performance Analyzer")

index_choice = st.radio("Select Index", ["S&P 500", "CSI 300"])

# Date input
def_ytd_start = datetime(datetime.today().year, 1, 1)
def_today = datetime.today()

start_date = st.date_input("Start Date", def_ytd_start)
end_date = st.date_input("End Date", def_today)

if start_date > end_date:
    st.error("⚠️ Start date must be before end date.")
    st.stop()

# Load metadata
if index_choice == "S&P 500":
    df_meta = get_sp500_metadata()
else:
    df_meta = load_csi300_metadata()

# Run performance calculation
with st.spinner("Fetching data and calculating performance..."):
    perf_df = get_performance(df_meta, start_date, end_date)

# Display output
st.subheader(f"Top 10 Performers: {index_choice}")
st.dataframe(perf_df[['Company Name', 'Ticker', 'Sector', 'Industry', 'Performance']].head(10), use_container_width=True)

st.subheader(f"Bottom 10 Performers: {index_choice}")
st.dataframe(perf_df[['Company Name', 'Ticker', 'Sector', 'Industry', 'Performance']].tail(10), use_container_width=True)

# Optional download
st.download_button("📥 Download Full Results", data=perf_df.to_csv(index=False), file_name=f"{index_choice}_performance.csv")
