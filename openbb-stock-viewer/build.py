"""Static HTML builder for the OpenBB-inspired stock viewer.

Fetches historical OHLCV data for a set of tickers and renders a
single self-contained ``index.html`` with interactive Plotly charts
and tab switching between tickers.

Data source: yfinance (which is the same underlying provider that
OpenBB's free ``yfinance`` provider uses). Keeping the dependency
footprint small makes the GitHub Action fast and free.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from jinja2 import Template
from plotly.subplots import make_subplots

MAX_RETRIES = 4
RETRY_BACKOFF = (2, 4, 8, 15)  # seconds between retries

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TICKERS: list[tuple[str, str]] = [
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("GOOGL", "Alphabet"),
    ("AMZN", "Amazon"),
    ("NVDA", "NVIDIA"),
    ("META", "Meta"),
    ("TSLA", "Tesla"),
]

PERIOD = "1y"
INTERVAL = "1d"
OUTPUT_FILE = Path(__file__).parent / "index.html"


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def _download_once(symbol: str) -> pd.DataFrame:
    df = yf.download(
        symbol,
        period=PERIOD,
        interval=INTERVAL,
        progress=False,
        auto_adjust=False,
        threads=False,
    )
    if df is None or df.empty:
        # Fall back to the Ticker.history() path — often succeeds when
        # the bulk download endpoint is rate-limited.
        df = yf.Ticker(symbol).history(
            period=PERIOD, interval=INTERVAL, auto_adjust=False
        )
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df


def fetch_prices(symbol: str) -> pd.DataFrame:
    """Download OHLCV data for a ticker with retries."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            df = _download_once(symbol)
            if not df.empty:
                return df
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"  retry {attempt + 1}/{MAX_RETRIES} for {symbol}: {exc}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF[attempt])
    if last_error:
        print(f"  final error for {symbol}: {last_error}")
    return pd.DataFrame()


def fetch_news(symbol: str, limit: int = 8) -> list[dict]:
    """Fetch latest news headlines for a ticker."""
    try:
        ticker = yf.Ticker(symbol)
        items = ticker.news or []
    except Exception:
        return []
    result: list[dict] = []
    for item in items[:limit]:
        content = item.get("content", item)
        title = content.get("title") or item.get("title") or "Untitled"
        url = (
            content.get("canonicalUrl", {}).get("url")
            or content.get("clickThroughUrl", {}).get("url")
            or item.get("link")
            or ""
        )
        publisher = (
            content.get("provider", {}).get("displayName")
            or item.get("publisher")
            or ""
        )
        pub_date = content.get("pubDate") or item.get("providerPublishTime") or ""
        if isinstance(pub_date, int):
            pub_date = datetime.fromtimestamp(pub_date, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
        elif isinstance(pub_date, str) and "T" in pub_date:
            pub_date = pub_date.split("T")[0]
        result.append(
            {
                "title": title,
                "url": url,
                "publisher": publisher,
                "date": pub_date,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Chart building
# ---------------------------------------------------------------------------
def build_chart(symbol: str, df: pd.DataFrame) -> go.Figure:
    """Build a candlestick + volume Plotly figure."""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=symbol,
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume",
            marker_color="#4fc3f7",
            opacity=0.6,
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        template="plotly_dark",
        height=560,
        xaxis_rangeslider_visible=False,
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font=dict(color="#e6e6e6"),
    )
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1, gridcolor="#1f2937")
    fig.update_yaxes(title_text="Volume", row=2, col=1, gridcolor="#1f2937")
    fig.update_xaxes(gridcolor="#1f2937")
    return fig


def stats_from_df(df: pd.DataFrame) -> dict:
    """Compute summary metrics shown above the chart."""
    last_close = float(df["Close"].iloc[-1])
    first_close = float(df["Close"].iloc[0])
    pct_change = (last_close - first_close) / first_close * 100
    return {
        "last_close": f"${last_close:,.2f}",
        "pct_change": f"{pct_change:+.2f}%",
        "pct_change_class": "up" if pct_change >= 0 else "down",
        "high": f"${float(df['High'].max()):,.2f}",
        "low": f"${float(df['Low'].min()):,.2f}",
        "bars": f"{len(df):,}",
    }


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Stock Viewer · OpenBB-inspired</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📈</text></svg>">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0e1117;
      color: #e6e6e6;
      min-height: 100vh;
      padding: 2rem 1rem;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    header { margin-bottom: 2rem; text-align: center; }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #4fc3f7; }
    .subtitle { color: #9aa4b2; font-size: 0.95rem; }
    .subtitle a { color: #4fc3f7; text-decoration: none; }
    .subtitle a:hover { text-decoration: underline; }
    .updated { color: #6c7a89; font-size: 0.85rem; margin-top: 0.5rem; }

    .tabs {
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
      justify-content: center;
    }
    .tab {
      background: #1a1f2e;
      border: 1px solid #2c3645;
      color: #e6e6e6;
      padding: 0.6rem 1.1rem;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
      font-size: 0.95rem;
      transition: all 0.15s;
    }
    .tab:hover { border-color: #4fc3f7; }
    .tab.active {
      background: #4fc3f7;
      color: #0e1117;
      border-color: #4fc3f7;
    }

    .panel { display: none; }
    .panel.active { display: block; }

    .card {
      background: #1a1f2e;
      border: 1px solid #2c3645;
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }

    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 1rem;
      margin-bottom: 1rem;
    }
    .stat-label { color: #9aa4b2; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .stat-value { font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }
    .stat-value.up { color: #26a69a; }
    .stat-value.down { color: #ef5350; }

    .ticker-name { font-size: 1.1rem; color: #9aa4b2; margin-bottom: 1rem; }

    .chart { width: 100%; height: 560px; }

    .news-title { font-size: 1.2rem; margin-bottom: 1rem; color: #4fc3f7; }
    .news-item {
      padding: 0.9rem 0;
      border-bottom: 1px solid #2c3645;
    }
    .news-item:last-child { border-bottom: none; }
    .news-item a { color: #e6e6e6; text-decoration: none; font-weight: 600; }
    .news-item a:hover { color: #4fc3f7; }
    .news-meta { color: #6c7a89; font-size: 0.85rem; margin-top: 0.3rem; }
    .news-empty { color: #6c7a89; font-style: italic; }

    footer {
      margin-top: 3rem;
      text-align: center;
      color: #6c7a89;
      font-size: 0.85rem;
    }
    footer a { color: #4fc3f7; text-decoration: none; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>📈 Stock Viewer</h1>
      <div class="subtitle">
        Inspired by <a href="https://github.com/OpenBB-finance/OpenBB" target="_blank" rel="noopener">OpenBB</a>
        · Free data from Yahoo Finance · Rebuilt daily by GitHub Actions
      </div>
      <div class="updated">Last updated: {{ updated_at }}</div>
    </header>

    <div class="tabs">
      {% for t in tickers %}
      <button class="tab {% if loop.first %}active{% endif %}" data-tab="{{ t.symbol }}">
        {{ t.symbol }}
      </button>
      {% endfor %}
    </div>

    {% for t in tickers %}
    <div class="panel {% if loop.first %}active{% endif %}" id="panel-{{ t.symbol }}">
      <div class="card">
        <div class="ticker-name">{{ t.name }} ({{ t.symbol }}) · 1Y daily</div>
        <div class="stats">
          <div>
            <div class="stat-label">Last close</div>
            <div class="stat-value">{{ t.stats.last_close }}</div>
          </div>
          <div>
            <div class="stat-label">1Y change</div>
            <div class="stat-value {{ t.stats.pct_change_class }}">{{ t.stats.pct_change }}</div>
          </div>
          <div>
            <div class="stat-label">1Y high</div>
            <div class="stat-value">{{ t.stats.high }}</div>
          </div>
          <div>
            <div class="stat-label">1Y low</div>
            <div class="stat-value">{{ t.stats.low }}</div>
          </div>
          <div>
            <div class="stat-label">Bars</div>
            <div class="stat-value">{{ t.stats.bars }}</div>
          </div>
        </div>
        <div class="chart" id="chart-{{ t.symbol }}"></div>
      </div>

      <div class="card">
        <div class="news-title">📰 Latest news</div>
        {% if t.news %}
          {% for n in t.news %}
          <div class="news-item">
            {% if n.url %}
            <a href="{{ n.url }}" target="_blank" rel="noopener">{{ n.title }}</a>
            {% else %}
            <span>{{ n.title }}</span>
            {% endif %}
            <div class="news-meta">
              {% if n.publisher %}{{ n.publisher }}{% endif %}
              {% if n.publisher and n.date %} · {% endif %}
              {% if n.date %}{{ n.date }}{% endif %}
            </div>
          </div>
          {% endfor %}
        {% else %}
          <div class="news-empty">No news available for this ticker.</div>
        {% endif %}
      </div>
    </div>
    {% endfor %}

    <footer>
      Built with <a href="https://github.com/OpenBB-finance/OpenBB" target="_blank" rel="noopener">OpenBB</a>
      inspiration, <a href="https://pypi.org/project/yfinance/" target="_blank" rel="noopener">yfinance</a>,
      <a href="https://plotly.com/" target="_blank" rel="noopener">Plotly</a> ·
      Source on <a href="https://github.com/eneskaya96/eneskaya.github.io/tree/main/openbb-stock-viewer" target="_blank" rel="noopener">GitHub</a>
    </footer>
  </div>

  <script>
    const figures = {{ figures_json | safe }};

    function renderAll() {
      for (const [symbol, fig] of Object.entries(figures)) {
        Plotly.newPlot('chart-' + symbol, fig.data, fig.layout, {responsive: true, displayModeBar: false});
      }
    }

    document.querySelectorAll('.tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b === btn));
        document.querySelectorAll('.panel').forEach(p => {
          p.classList.toggle('active', p.id === 'panel-' + target);
        });
        // Plotly needs a resize trigger when a hidden chart becomes visible
        window.dispatchEvent(new Event('resize'));
      });
    });

    renderAll();
  </script>
</body>
</html>
"""
)


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------
def main() -> None:
    ticker_data = []
    figures = {}
    for idx, (symbol, name) in enumerate(TICKERS):
        if idx > 0:
            time.sleep(1.5)  # be gentle on Yahoo's rate limits
        print(f"→ Fetching {symbol} …")
        df = fetch_prices(symbol)
        if df.empty:
            print(f"  ⚠️  No data for {symbol}, skipping")
            continue
        fig = build_chart(symbol, df)
        figures[symbol] = json.loads(fig.to_json())
        ticker_data.append(
            {
                "symbol": symbol,
                "name": name,
                "stats": stats_from_df(df),
                "news": fetch_news(symbol),
            }
        )

    if not ticker_data:
        print("❌ No ticker data fetched — leaving existing index.html untouched.")
        raise SystemExit(1)

    html = HTML_TEMPLATE.render(
        tickers=ticker_data,
        figures_json=json.dumps(figures),
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"✅ Wrote {OUTPUT_FILE} ({len(html):,} bytes, {len(ticker_data)} tickers)")


if __name__ == "__main__":
    main()
