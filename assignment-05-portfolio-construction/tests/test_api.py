import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_life_stages_endpoint():
    response = client.get("/life-stages")
    assert response.status_code == 200
    stages = response.json()
    assert "Growth" in stages
    assert "Retirement" in stages
    assert len(stages) == 5


def test_portfolio_invalid_life_stage():
    response = client.post("/portfolio", json={"life_stage": "Invalid Stage"})
    assert response.status_code == 422


@pytest.fixture
def mock_portfolio_response():
    from app.models import (
        DataProvenance,
        PortfolioMetrics,
        PortfolioResponse,
        PortfolioStock,
        ScreeningSummary,
        Verification,
    )

    def make_stock(rank: int):
        return PortfolioStock(
            rank=rank,
            ticker=f"T{rank}",
            company_name=f"Company {rank}",
            sector="Information Technology",
            weight_pct=10.0,
            jensen_alpha=8.0,
            beta=1.1,
            annualized_return=20.0,
            volatility=18.0,
            max_drawdown=-22.0,
            rationale="Strong alpha.",
            portfolio_role="Core tech.",
            key_risk="Valuation.",
        )

    return PortfolioResponse(
        investor_profile={
            "life_stage": "Growth",
            "beta_cap": 1.2,
            "max_drawdown_limit": "25%",
            "min_alpha_target_pct": 4.0,
        },
        screening_summary=ScreeningSummary(
            universe_size=503,
            post_beta_filter_count=320,
            post_drawdown_filter_count=280,
            risk_free_rate_used=4.3,
            spy_annualized_return=12.0,
            top_15_candidates=[],
        ),
        portfolio=[make_stock(i) for i in range(1, 11)],
        portfolio_metrics=PortfolioMetrics(
            weighted_avg_beta=1.05,
            weighted_avg_alpha_pct=6.5,
            expected_annualized_return_pct=18.5,
            portfolio_max_drawdown_pct=-20.0,
            sharpe_ratio=1.2,
            total_weight_pct=100.0,
            alpha_target_met=True,
        ),
        verification=Verification(
            stock_count_ok=True,
            sp500_membership_ok=True,
            beta_cap_ok=True,
            drawdown_constraint_ok=True,
            sector_concentration_ok=True,
            alpha_target_ok=True,
            weights_sum_ok=True,
            all_checks_passed=True,
            corrections_made="None",
        ),
        data_provenance=DataProvenance(
            data_source="yfinance",
            lookback_period="3 years monthly",
            benchmark="SPY",
            risk_free_rate=4.3,
            data_as_of="2026-05-14",
        ),
        warnings=[],
    )


def test_portfolio_valid_request_mocked(mock_portfolio_response):
    with patch("app.main.run_portfolio_pipeline") as mock_run:
        mock_run.return_value = mock_portfolio_response
        response = client.post("/portfolio", json={"life_stage": "Growth"})
    assert response.status_code == 200
    data = response.json()
    assert "portfolio" in data
    assert len(data["portfolio"]) == 10
