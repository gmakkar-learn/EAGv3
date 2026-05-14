import numpy as np
import pandas as pd
import pytest

from app.portfolio_engine import (
    compute_annualized_return,
    compute_beta,
    compute_jensen_alpha,
    compute_max_drawdown,
    compute_volatility,
)


def test_compute_beta_perfect_correlation():
    market = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01])
    stock = market * 1.5
    beta = compute_beta(stock, market)
    assert abs(beta - 1.5) < 0.01


def test_compute_beta_uncorrelated():
    rng = np.random.default_rng(42)
    market = pd.Series(rng.normal(0, 0.02, 100))
    stock = pd.Series(rng.normal(0, 0.02, 100))
    beta = compute_beta(stock, market)
    assert abs(beta) < 0.3


def test_compute_max_drawdown_known_series():
    prices = pd.Series([100.0, 120.0, 80.0, 90.0])
    mdd = compute_max_drawdown(prices)
    # peak=120, trough=80: (80-120)/120 = -33.33%
    assert abs(mdd - (-33.33)) < 0.1


def test_compute_max_drawdown_no_drawdown():
    prices = pd.Series([100.0, 110.0, 120.0, 130.0])
    mdd = compute_max_drawdown(prices)
    assert mdd == 0.0


def test_compute_jensen_alpha():
    # stock=20%, beta=1.2, market=15%, rfr=4%
    # CAPM = 4 + 1.2*(15-4) = 17.2% → alpha = 2.8%
    alpha = compute_jensen_alpha(
        stock_return=20.0, beta=1.2, market_return=15.0, risk_free_rate=4.0
    )
    assert abs(alpha - 2.8) < 0.01


def test_compute_annualized_return():
    # 3-year 50% total return → ~14.47% annualized
    ret = compute_annualized_return(total_return_pct=50.0, years=3)
    assert abs(ret - 14.47) < 0.1


def test_compute_volatility():
    monthly_returns = pd.Series([0.02, -0.01, 0.03, -0.02, 0.01])
    vol = compute_volatility(monthly_returns)
    expected = monthly_returns.std() * (12**0.5) * 100
    assert abs(vol - expected) < 0.01
