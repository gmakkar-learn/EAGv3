import numpy as np
import pandas as pd
from scipy import stats

from app.models import LifeStageProfile, StockMetrics


def compute_beta(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    aligned = pd.DataFrame({"s": stock_returns, "m": market_returns}).dropna()
    if len(aligned) < 5:
        return 1.0
    slope, _, _, _, _ = stats.linregress(aligned["m"], aligned["s"])
    return round(float(slope), 4)


def compute_max_drawdown(prices: pd.Series) -> float:
    """Returns max drawdown as a negative percentage (e.g. -25.3)."""
    if prices.empty:
        return 0.0
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax * 100
    return round(float(drawdown.min()), 2)


def compute_jensen_alpha(
    stock_return: float,
    beta: float,
    market_return: float,
    risk_free_rate: float,
) -> float:
    """All inputs and output in percent."""
    capm_expected = risk_free_rate + beta * (market_return - risk_free_rate)
    return round(stock_return - capm_expected, 4)


def compute_annualized_return(total_return_pct: float, years: int = 3) -> float:
    total = total_return_pct / 100
    annualized = ((1 + total) ** (1 / years) - 1) * 100
    return round(annualized, 4)


def compute_volatility(monthly_returns: pd.Series) -> float:
    """Annualized volatility in percent."""
    return round(float(monthly_returns.std() * (12**0.5) * 100), 4)


def compute_all_metrics(
    tickers: list[str],
    prices_df: pd.DataFrame,
    spy_prices: pd.Series,
    risk_free_rate: float,
    spy_annualized_return: float,
    company_info: dict[str, dict],
    years: int = 3,
) -> list[StockMetrics]:
    # Normalize timezone so tz-aware and tz-naive series can align
    if spy_prices.index.tz is not None:
        spy_prices = spy_prices.copy()
        spy_prices.index = spy_prices.index.tz_localize(None)

    spy_returns = spy_prices.pct_change().dropna()
    results = []

    for ticker in tickers:
        if ticker not in prices_df.columns:
            continue
        series = prices_df[ticker].dropna()
        if series.index.tz is not None:
            series = series.copy()
            series.index = series.index.tz_localize(None)
        if len(series) < 12:
            continue

        monthly_returns = series.pct_change().dropna()
        total_return_pct = (series.iloc[-1] / series.iloc[0] - 1) * 100
        ann_return = compute_annualized_return(float(total_return_pct), years)
        beta = compute_beta(monthly_returns, spy_returns)
        vol = compute_volatility(monthly_returns)
        mdd = compute_max_drawdown(series)
        alpha = compute_jensen_alpha(ann_return, beta, spy_annualized_return, risk_free_rate)

        info = company_info.get(ticker, {})
        results.append(
            StockMetrics(
                ticker=ticker,
                company_name=info.get("company_name", ticker),
                sector=info.get("sector", "Unknown"),
                jensen_alpha=alpha,
                beta=beta,
                annualized_return=ann_return,
                volatility=vol,
                max_drawdown=mdd,
            )
        )

    return results


def screen_universe(
    metrics: list[StockMetrics],
    profile: LifeStageProfile,
) -> tuple[list[StockMetrics], int, int]:
    """Returns (screened_list, post_beta_count, post_drawdown_count)."""
    post_beta = [s for s in metrics if s.beta <= profile.beta_cap]
    if profile.max_drawdown_limit is None:
        post_drawdown = post_beta
    else:
        post_drawdown = [
            s for s in post_beta if s.max_drawdown >= -profile.max_drawdown_limit
        ]
    return post_drawdown, len(post_beta), len(post_drawdown)


def rank_by_alpha(screened: list[StockMetrics]) -> list[StockMetrics]:
    return sorted(screened, key=lambda s: s.jensen_alpha, reverse=True)


def apply_sector_cap(
    ranked: list[StockMetrics],
    top_n: int = 15,
    max_per_sector: int = 3,
) -> list[StockMetrics]:
    """Return top_n candidates with max_per_sector cap per GICS sector."""
    sector_counts: dict[str, int] = {}
    selected = []
    for stock in ranked:
        count = sector_counts.get(stock.sector, 0)
        if count < max_per_sector:
            selected.append(stock)
            sector_counts[stock.sector] = count + 1
        if len(selected) == top_n:
            break
    return selected
