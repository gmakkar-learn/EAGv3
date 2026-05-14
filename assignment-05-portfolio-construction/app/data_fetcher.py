import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
TICKERS_CACHE = CACHE_DIR / "sp500_tickers.json"
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)


def get_sp500_tickers() -> list[str]:
    if _cache_is_fresh(TICKERS_CACHE):
        return json.loads(TICKERS_CACHE.read_text())

    table = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", header=0
    )[0]
    tickers = table["Symbol"].str.replace(".", "-", regex=False).tolist()
    TICKERS_CACHE.write_text(json.dumps(tickers))
    return tickers


def get_sp500_company_info() -> dict[str, dict]:
    """Returns {ticker: {company_name, sector}} for all S&P 500 constituents."""
    table = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", header=0
    )[0]
    return {
        row["Symbol"].replace(".", "-"): {
            "company_name": row["Security"],
            "sector": row["GICS Sector"],
        }
        for _, row in table.iterrows()
    }


def get_monthly_prices(tickers: list[str], years: int = 3) -> pd.DataFrame:
    cache_key = CACHE_DIR / f"prices_{years}y_{len(tickers)}.parquet"
    if _cache_is_fresh(cache_key):
        return pd.read_parquet(cache_key)

    raw = yf.download(
        tickers,
        period=f"{years}y",
        interval="1mo",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"].dropna(how="all")
    else:
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

    prices.to_parquet(cache_key)
    return prices


def get_spy_annualized_return(years: int = 3) -> float:
    prices = get_monthly_prices(["SPY"], years=years)
    col = "SPY"
    total_return = prices[col].iloc[-1] / prices[col].iloc[0] - 1
    annualized = (1 + total_return) ** (1 / years) - 1
    return round(float(annualized) * 100, 2)


def get_risk_free_rate() -> float:
    """Fetch current 10-yr US Treasury yield (^TNX). Returns percentage."""
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 4.3  # fallback: US 10-yr Treasury default as of 2025
