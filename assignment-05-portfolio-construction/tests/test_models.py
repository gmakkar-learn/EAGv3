import pytest
from app.models import (
    LIFE_STAGE_PROFILES,
    LifeStage,
    PortfolioRequest,
    PortfolioStock,
    StockMetrics,
)


def test_life_stage_enum_values():
    assert LifeStage.EARLY_INVESTOR == "Early Investor"
    assert LifeStage.RETIREMENT == "Retirement"


def test_life_stage_profiles_coverage():
    for stage in LifeStage:
        assert stage in LIFE_STAGE_PROFILES
        profile = LIFE_STAGE_PROFILES[stage]
        assert profile.beta_cap > 0
        assert profile.min_alpha_target_pct >= 4.0


def test_portfolio_request_valid():
    req = PortfolioRequest(life_stage=LifeStage.GROWTH)
    assert req.life_stage == LifeStage.GROWTH


def test_stock_metrics_fields():
    s = StockMetrics(
        ticker="AAPL",
        company_name="Apple Inc.",
        sector="Information Technology",
        jensen_alpha=8.5,
        beta=1.2,
        annualized_return=22.0,
        volatility=18.0,
        max_drawdown=-25.0,
    )
    assert s.ticker == "AAPL"
    assert s.max_drawdown < 0


def test_portfolio_response_round_trip():
    stock = PortfolioStock(
        rank=1,
        ticker="AAPL",
        company_name="Apple Inc.",
        sector="Information Technology",
        weight_pct=15.0,
        jensen_alpha=8.5,
        beta=1.2,
        annualized_return=22.0,
        volatility=18.0,
        max_drawdown=-25.0,
        rationale="Strong alpha driver.",
        portfolio_role="Core tech.",
        key_risk="Valuation.",
    )
    assert stock.weight_pct == 15.0
