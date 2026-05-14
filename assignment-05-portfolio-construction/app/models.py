from enum import Enum
from typing import Optional

from pydantic import BaseModel


class LifeStage(str, Enum):
    EARLY_INVESTOR = "Early Investor"
    ACCELERATE = "Accelerate"
    GROWTH = "Growth"
    PROTECT = "Protect"
    RETIREMENT = "Retirement"


class LifeStageProfile(BaseModel):
    beta_cap: float
    max_drawdown_limit: Optional[float]  # None = unconstrained
    min_alpha_target_pct: float
    volatility_preference: str


LIFE_STAGE_PROFILES: dict[LifeStage, LifeStageProfile] = {
    LifeStage.EARLY_INVESTOR: LifeStageProfile(
        beta_cap=2.0,
        max_drawdown_limit=None,
        min_alpha_target_pct=6.0,
        volatility_preference="High-beta, long-term growth",
    ),
    LifeStage.ACCELERATE: LifeStageProfile(
        beta_cap=1.5,
        max_drawdown_limit=35.0,
        min_alpha_target_pct=5.0,
        volatility_preference="Moderate-high growth",
    ),
    LifeStage.GROWTH: LifeStageProfile(
        beta_cap=1.2,
        max_drawdown_limit=25.0,
        min_alpha_target_pct=4.0,
        volatility_preference="Balanced growth/quality",
    ),
    LifeStage.PROTECT: LifeStageProfile(
        beta_cap=1.0,
        max_drawdown_limit=20.0,
        min_alpha_target_pct=4.0,
        volatility_preference="Low-volatility quality",
    ),
    LifeStage.RETIREMENT: LifeStageProfile(
        beta_cap=0.8,
        max_drawdown_limit=15.0,
        min_alpha_target_pct=4.0,
        volatility_preference="Capital preservation + alpha",
    ),
}


class PortfolioRequest(BaseModel):
    life_stage: LifeStage


class StockMetrics(BaseModel):
    ticker: str
    company_name: str
    sector: str
    jensen_alpha: float
    beta: float
    annualized_return: float
    volatility: float
    max_drawdown: float  # negative float, e.g. -25.0 means -25%


class PortfolioStock(StockMetrics):
    rank: int
    weight_pct: float
    rationale: str
    portfolio_role: str
    key_risk: str


class ScreeningSummary(BaseModel):
    universe_size: int
    post_beta_filter_count: int
    post_drawdown_filter_count: int
    risk_free_rate_used: float
    spy_annualized_return: float
    top_15_candidates: list[StockMetrics]


class PortfolioMetrics(BaseModel):
    weighted_avg_beta: float
    weighted_avg_alpha_pct: float
    expected_annualized_return_pct: float
    portfolio_max_drawdown_pct: float
    sharpe_ratio: float
    total_weight_pct: float
    alpha_target_met: bool


class Verification(BaseModel):
    stock_count_ok: bool
    sp500_membership_ok: bool
    beta_cap_ok: bool
    drawdown_constraint_ok: bool
    sector_concentration_ok: bool
    alpha_target_ok: bool
    weights_sum_ok: bool
    all_checks_passed: bool
    corrections_made: str


class DataProvenance(BaseModel):
    data_source: str
    lookback_period: str
    benchmark: str
    risk_free_rate: float
    data_as_of: str


class PortfolioResponse(BaseModel):
    investor_profile: dict
    screening_summary: ScreeningSummary
    portfolio: list[PortfolioStock]
    portfolio_metrics: PortfolioMetrics
    verification: Verification
    data_provenance: DataProvenance
    warnings: list[str]
