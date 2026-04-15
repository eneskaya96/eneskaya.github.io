# 📈 OpenBB Stock Viewer

A tiny, free Streamlit dashboard that shows candlestick charts, upcoming
earnings and the latest company news for any ticker — powered entirely
by [OpenBB](https://github.com/OpenBB-finance/OpenBB) and the free
Yahoo Finance provider.

**No API key required.** You can run and deploy this without paying
anything.

## Features

- 📊 Interactive candlestick chart with volume (Plotly, dark theme)
- 📅 Upcoming earnings calendar
- 📰 Latest company news
- 🔍 Enter any ticker — `AAPL`, `MSFT`, `GOOGL`, `TSLA`, …
- ⚡ Cached API calls so repeat loads are instant

## Quick start

```bash
# 1. Clone / copy this folder
cd openbb-stock-viewer

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate     # on Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The app will open at <http://localhost:8501>.

## Deploy for free

This app is ready to deploy to
[Streamlit Community Cloud](https://streamlit.io/cloud):

1. Push this folder to a GitHub repo
2. Connect the repo on Streamlit Community Cloud
3. Point it at `app.py` — that's it

## How it works

The app uses three OpenBB endpoints via the `openbb` Python package:

| Feature      | OpenBB call                           | Provider(s) tried              |
| ------------ | ------------------------------------- | ------------------------------ |
| Candlestick  | `obb.equity.price.historical()`       | `yfinance`                     |
| Earnings     | `obb.equity.calendar.earnings()`      | `yfinance`, `nasdaq`, `seeking_alpha` |
| News         | `obb.news.company()`                  | `yfinance`, `benzinga`, `tiingo` |

Each call is wrapped in `@st.cache_data` so Streamlit re-uses the
results between reruns (15 minutes for prices, 30 minutes for news,
1 hour for earnings).

For earnings and news, the app tries several free providers in order
because not every provider exposes data for every ticker.

## Notes

- OpenBB itself is AGPLv3 — this app only **uses** the library, it does
  not fork or redistribute it.
- Some OpenBB extensions need API keys for premium providers (Polygon,
  FMP, Tiingo, Benzinga, …). This app only relies on free, key-less
  providers so it works out-of-the-box.

## License

MIT
