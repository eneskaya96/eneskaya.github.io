# 📈 Stock Viewer

Small, fully free stock dashboard inspired by
[OpenBB](https://github.com/OpenBB-finance/OpenBB).

Two flavours live side by side in this folder:

| File        | Purpose                                                          |
| ----------- | ---------------------------------------------------------------- |
| `build.py`  | **Static site generator.** Renders `index.html` with Plotly charts, stats and news for a preset list of tickers. Runs in GitHub Actions daily, deployed via GitHub Pages — **no server, no API key, no paid service**. |
| `app.py`    | **Interactive Streamlit app** using the full OpenBB Python SDK. Lets you enter any ticker locally. |

## 🌐 Live deployment

The static version is rebuilt by GitHub Actions every weekday after US
market close and published through GitHub Pages at:

**<https://eneskaya.github.io/openbb-stock-viewer/>**

Tickers currently tracked: **AAPL · MSFT · GOOGL · AMZN · NVDA · META · TSLA**.

To add or remove tickers, edit the `TICKERS` list at the top of
`build.py` and push — the Action will rebuild on the next cron tick
(or trigger it manually from the Actions tab).

## 🧰 How it works

```
          ┌─────────────────────┐
          │  GitHub Actions     │     weekdays @ 22:30 UTC
          │  build-stock-viewer │──────────── cron ────────┐
          └──────────┬──────────┘                          │
                     │                                     │
                     ▼                                     │
          ┌─────────────────────┐                          │
          │ python build.py     │                          │
          │ yfinance → plotly   │                          │
          │ → openbb-stock-     │                          │
          │   viewer/index.html │                          │
          └──────────┬──────────┘                          │
                     │ git commit + push                   │
                     ▼                                     │
          ┌─────────────────────┐                          │
          │ GitHub Pages        │ ◄────────────────────────┘
          │ eneskaya.github.io/ │
          │ openbb-stock-viewer │
          └─────────────────────┘
```

`build.py` uses [`yfinance`](https://pypi.org/project/yfinance/) — the
same underlying data source OpenBB ships as its free default provider.
We call it directly here to keep the Action footprint tiny (pulling in
the full `openbb` meta-package in CI takes minutes for no real benefit
in a static build).

`app.py` is kept for local experimentation with the full OpenBB SDK —
you can try different providers (Nasdaq, FMP, Tiingo, …) and endpoints.

## 🖥 Run locally

### Static build (what production uses)

```bash
python -m venv .venv && source .venv/bin/activate
pip install yfinance plotly pandas jinja2
python build.py
# Open index.html in your browser
```

### Streamlit app (full OpenBB SDK, interactive)

```bash
pip install -r requirements.txt
streamlit run app.py
# → http://localhost:8501
```

## 💰 Is it really free?

Yes:

- **OpenBB** — AGPLv3 open source, free.
- **yfinance** — free, no API key required.
- **GitHub Actions** — free tier covers this easily (a few minutes
  of Ubuntu runner per day).
- **GitHub Pages** — free static hosting.
- **Plotly.js** — BSD-licensed, loaded from CDN.

Total cost: **$0**.

## 📝 Notes

- OpenBB itself is AGPLv3 — this project only **uses** its ideas and
  data approach, it doesn't fork or redistribute OpenBB.
- Premium providers (Polygon, FMP, Benzinga, …) need API keys. This
  project only depends on free, key-less data, so it runs out of the
  box.

## 📄 License

MIT
