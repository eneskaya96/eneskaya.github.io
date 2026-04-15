"""Stock Viewer — OpenBB + Streamlit demo.

Interactive dashboard that shows candlestick charts, upcoming earnings,
and the latest company news for any ticker, using OpenBB's free
Yahoo Finance provider (no API key required).
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from openbb import obb


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock Viewer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


PERIODS: dict[str, timedelta] = {
    "1M": timedelta(days=30),
    "3M": timedelta(days=90),
    "6M": timedelta(days=180),
    "1Y": timedelta(days=365),
    "5Y": timedelta(days=365 * 5),
}


# ---------------------------------------------------------------------------
# Data fetching (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def get_prices(symbol: str, start: date, end: date, interval: str) -> pd.DataFrame:
    """Historical OHLCV prices via OpenBB + yfinance."""
    out = obb.equity.price.historical(
        symbol=symbol,
        start_date=start,
        end_date=end,
        interval=interval,
        provider="yfinance",
    )
    df = out.to_dataframe()
    if df.empty:
        return df
    # Ensure a DatetimeIndex for plotly
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings(symbol: str) -> pd.DataFrame:
    """Upcoming / historical earnings calendar.

    Tries a few free providers in order because not every provider
    supports every symbol. Returns an empty DataFrame if none work.
    """
    providers = ("yfinance", "nasdaq", "seeking_alpha")
    for provider in providers:
        try:
            out = obb.equity.calendar.earnings(symbol=symbol, provider=provider)
            df = out.to_dataframe()
            if not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def get_news(symbol: str, limit: int = 10) -> pd.DataFrame:
    """Latest company news."""
    providers = ("yfinance", "benzinga", "tiingo")
    for provider in providers:
        try:
            out = obb.news.company(symbol=symbol, limit=limit, provider=provider)
            df = out.to_dataframe()
            if not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Sidebar — user inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📈 Stock Viewer")
    st.caption("Powered by OpenBB · Yahoo Finance")

    symbol = st.text_input("Ticker", value="AAPL").strip().upper()
    period_label = st.selectbox("Period", list(PERIODS.keys()), index=3)
    interval = st.selectbox("Interval", ["1d", "1W", "1M"], index=0)

    st.markdown("---")
    st.markdown(
        "**Tip:** Yahoo Finance provider requires no API key — "
        "this app runs fully free."
    )

end_date = date.today()
start_date = end_date - PERIODS[period_label]


# ---------------------------------------------------------------------------
# Main — fetch price data for header metrics
# ---------------------------------------------------------------------------
if not symbol:
    st.info("Enter a ticker in the sidebar to get started.")
    st.stop()

try:
    prices = get_prices(symbol, start_date, end_date, interval)
except Exception as exc:  # noqa: BLE001
    st.error(f"Failed to load price data for **{symbol}**: {exc}")
    st.stop()

if prices.empty:
    st.error(f"No price data returned for **{symbol}**. Is the ticker valid?")
    st.stop()

# Header metrics
last_close = float(prices["close"].iloc[-1])
first_close = float(prices["close"].iloc[0])
pct_change = (last_close - first_close) / first_close * 100
period_high = float(prices["high"].max())
period_low = float(prices["low"].min())

st.title(f"{symbol}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Last Close", f"${last_close:,.2f}", f"{pct_change:+.2f}%")
c2.metric(f"{period_label} High", f"${period_high:,.2f}")
c3.metric(f"{period_label} Low", f"${period_low:,.2f}")
c4.metric("Bars", f"{len(prices):,}")

st.markdown("---")


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_chart, tab_earnings, tab_news = st.tabs(
    ["📊 Candlestick", "📅 Earnings", "📰 News"]
)

# --- Candlestick tab -------------------------------------------------------
with tab_chart:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )
    fig.add_trace(
        go.Candlestick(
            x=prices.index,
            open=prices["open"],
            high=prices["high"],
            low=prices["low"],
            close=prices["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    if "volume" in prices.columns:
        fig.add_trace(
            go.Bar(
                x=prices.index,
                y=prices["volume"],
                name="Volume",
                marker_color="#6c7a89",
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        template="plotly_dark",
        height=640,
        xaxis_rangeslider_visible=False,
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    st.plotly_chart(fig, use_container_width=True)

# --- Earnings tab ----------------------------------------------------------
with tab_earnings:
    st.subheader(f"Earnings calendar — {symbol}")
    earnings_df = get_earnings(symbol)
    if earnings_df.empty:
        st.info("No earnings data available for this ticker from the free providers.")
    else:
        st.dataframe(earnings_df, use_container_width=True)

# --- News tab --------------------------------------------------------------
with tab_news:
    st.subheader(f"Latest news — {symbol}")
    news_df = get_news(symbol, limit=15)
    if news_df.empty:
        st.info("No news available for this ticker from the free providers.")
    else:
        for _, row in news_df.iterrows():
            title = row.get("title") or row.get("headline") or "Untitled"
            url = row.get("url") or row.get("link") or ""
            published = row.get("date") or row.get("published") or ""
            source = row.get("source") or row.get("publisher") or ""
            header = f"**[{title}]({url})**" if url else f"**{title}**"
            meta = " · ".join(str(x) for x in (source, published) if x)
            st.markdown(header)
            if meta:
                st.caption(meta)
            st.markdown("---")
