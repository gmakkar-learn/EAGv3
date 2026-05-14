# Portfolio Construction App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + Pydantic application that constructs a Jensen's Alpha-maximizing 10-stock S&P 500 portfolio tailored to an investor's life stage, powered by Claude as the reasoning engine.

**Architecture:** Python fetches and pre-processes S&P 500 market data (prices, beta, drawdown, alpha) via yfinance, screens the universe through steps 1–3 of the portfolio construction protocol, then passes the top 15 candidates to Claude (with the system prompt from `portfolio_construction_prompt.md`) to perform steps 4–7 (weighting, portfolio metrics, self-verification, rationale). Claude returns structured JSON; FastAPI validates it with Pydantic and serves it to a minimal HTML frontend.

**Tech Stack:** FastAPI 0.115, Pydantic v2, yfinance 0.2, pandas, numpy, Anthropic Python SDK, uvicorn, python-dotenv

---

## File Structure

```
assignment-05-portfolio-construction/
├── app/
│   ├── __init__.py            # empty
│   ├── main.py                # FastAPI app, routes, static file mount
│   ├── models.py              # All Pydantic models (request + response)
│   ├── data_fetcher.py        # yfinance S&P500 data + disk cache
│   ├── portfolio_engine.py    # Beta, drawdown, alpha computation + screening
│   └── llm_agent.py           # Claude API call for steps 4–7
├── static/
│   └── index.html             # Frontend: dropdown + results display
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_portfolio_engine.py
│   └── test_api.py
├── portfolio_construction_prompt.md   # Already exists — system prompt
├── requirements.txt
├── .env.example
└── .env                               # gitignored
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write requirements.txt**

```text
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.7.0
yfinance==0.2.40
pandas==2.2.2
numpy==1.26.4
anthropic==0.34.0
python-dotenv==1.0.1
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.7
httpx==0.27.0
```

- [ ] **Step 2: Write .env.example**

```text
ANTHROPIC_API_KEY=your_anthropic_api_key_here
CACHE_TTL_HOURS=24
```

- [ ] **Step 3: Create empty init files**

```bash
mkdir -p app tests static
touch app/__init__.py tests/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: All packages install without errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example app/__init__.py tests/__init__.py
git commit -m "feat: scaffold portfolio construction app"
```

---

## Task 2: Pydantic Models

**Files:**
- Create: `app/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
import pytest
from app.models import (
    LifeStage, PortfolioRequest, StockMetrics, PortfolioStock,
    ScreeningSummary, PortfolioMetrics, Verification, DataProvenance,
    PortfolioResponse, LIFE_STAGE_PROFILES
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
        ticker="AAPL", company_name="Apple Inc.", sector="Information Technology",
        jensen_alpha=8.5, beta=1.2, annualized_return=22.0,
        volatility=18.0, max_drawdown=-25.0
    )
    assert s.ticker == "AAPL"
    assert s.max_drawdown < 0

def test_portfolio_response_round_trip():
    stock = PortfolioStock(
        rank=1, ticker="AAPL", company_name="Apple Inc.",
        sector="Information Technology", weight_pct=15.0,
        jensen_alpha=8.5, beta=1.2, annualized_return=22.0,
        volatility=18.0, max_drawdown=-25.0,
        rationale="Strong alpha driver.", portfolio_role="Core tech.", key_risk="Valuation."
    )
    assert stock.weight_pct == 15.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write app/models.py**

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class LifeStage(str, Enum):
    EARLY_INVESTOR = "Early Investor"
    ACCELERATE = "Accelerate"
    GROWTH = "Growth"
    PROTECT = "Protect"
    RETIREMENT = "Retirement"


class LifeStageProfile(BaseModel):
    beta_cap: float
    max_drawdown_limit: Optional[float]   # None means unconstrained
    min_alpha_target_pct: float
    volatility_preference: str


LIFE_STAGE_PROFILES: dict[LifeStage, LifeStageProfile] = {
    LifeStage.EARLY_INVESTOR: LifeStageProfile(
        beta_cap=2.0, max_drawdown_limit=None,
        min_alpha_target_pct=6.0, volatility_preference="High-beta, long-term growth"
    ),
    LifeStage.ACCELERATE: LifeStageProfile(
        beta_cap=1.5, max_drawdown_limit=35.0,
        min_alpha_target_pct=5.0, volatility_preference="Moderate-high growth"
    ),
    LifeStage.GROWTH: LifeStageProfile(
        beta_cap=1.2, max_drawdown_limit=25.0,
        min_alpha_target_pct=4.0, volatility_preference="Balanced growth/quality"
    ),
    LifeStage.PROTECT: LifeStageProfile(
        beta_cap=1.0, max_drawdown_limit=20.0,
        min_alpha_target_pct=4.0, volatility_preference="Low-volatility quality"
    ),
    LifeStage.RETIREMENT: LifeStageProfile(
        beta_cap=0.8, max_drawdown_limit=15.0,
        min_alpha_target_pct=4.0, volatility_preference="Capital preservation + alpha"
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
    max_drawdown: float       # negative float, e.g. -25.0 means -25%


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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add Pydantic models for portfolio construction"
```

---

## Task 3: S&P 500 Data Fetcher with Disk Cache

**Files:**
- Create: `app/data_fetcher.py`
- Create: `tests/test_data_fetcher.py` (light integration test — hits network)

- [ ] **Step 1: Write failing test**

```python
# tests/test_data_fetcher.py
import pandas as pd
from app.data_fetcher import get_sp500_tickers, get_monthly_prices, get_risk_free_rate

def test_get_sp500_tickers_returns_list():
    tickers = get_sp500_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) > 490
    assert "AAPL" in tickers
    assert "MSFT" in tickers

def test_get_monthly_prices_shape():
    prices = get_monthly_prices(["AAPL", "MSFT", "GOOGL"], years=1)
    assert isinstance(prices, pd.DataFrame)
    assert set(["AAPL", "MSFT", "GOOGL"]).issubset(prices.columns)
    assert len(prices) >= 10  # at least 10 monthly rows in 1 year

def test_risk_free_rate_is_reasonable():
    rfr = get_risk_free_rate()
    assert isinstance(rfr, float)
    assert 0.0 < rfr < 15.0  # sanity: between 0% and 15%
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_data_fetcher.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write app/data_fetcher.py**

```python
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)
TICKERS_CACHE = CACHE_DIR / "sp500_tickers.json"
PRICES_CACHE = CACHE_DIR / "monthly_prices.parquet"
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


def get_monthly_prices(tickers: list[str], years: int = 3) -> pd.DataFrame:
    cache_key = CACHE_DIR / f"prices_{years}y_{len(tickers)}.parquet"
    if _cache_is_fresh(cache_key):
        return pd.read_parquet(cache_key)

    period = f"{years}y"
    raw = yf.download(
        tickers, period=period, interval="1mo",
        auto_adjust=True, progress=False, threads=True
    )
    # yf returns MultiIndex when multiple tickers; extract Close
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
    return round(annualized * 100, 2)  # return as percentage


def get_risk_free_rate() -> float:
    """Fetch current 10-yr US Treasury yield (^TNX). Returns percentage."""
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 4.3  # fallback default
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_data_fetcher.py -v
```

Expected: All 3 PASS (may take ~20–30 seconds on first run due to network).

- [ ] **Step 5: Commit**

```bash
git add app/data_fetcher.py tests/test_data_fetcher.py
git commit -m "feat: add S&P500 data fetcher with disk cache"
```

---

## Task 4: Quantitative Metrics Engine

**Files:**
- Create: `app/portfolio_engine.py`
- Create: `tests/test_portfolio_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_portfolio_engine.py
import numpy as np
import pandas as pd
import pytest
from app.portfolio_engine import (
    compute_beta, compute_max_drawdown, compute_jensen_alpha,
    compute_annualized_return, compute_volatility
)

def test_compute_beta_perfect_correlation():
    market = pd.Series([0.01, -0.02, 0.03, 0.01, -0.01])
    stock = market * 1.5  # beta should be 1.5
    beta = compute_beta(stock, market)
    assert abs(beta - 1.5) < 0.01

def test_compute_beta_uncorrelated():
    rng = np.random.default_rng(42)
    market = pd.Series(rng.normal(0, 0.02, 100))
    stock = pd.Series(rng.normal(0, 0.02, 100))  # random, beta ~0
    beta = compute_beta(stock, market)
    assert abs(beta) < 0.3  # low beta for uncorrelated series

def test_compute_max_drawdown_known_series():
    # prices go 100 -> 120 -> 80 -> 90
    prices = pd.Series([100.0, 120.0, 80.0, 90.0])
    mdd = compute_max_drawdown(prices)
    # peak=120, trough=80, drawdown = (80-120)/120 = -33.33%
    assert abs(mdd - (-33.33)) < 0.1

def test_compute_max_drawdown_no_drawdown():
    prices = pd.Series([100.0, 110.0, 120.0, 130.0])
    mdd = compute_max_drawdown(prices)
    assert mdd == 0.0

def test_compute_jensen_alpha():
    # stock returned 20%, beta=1.2, market=15%, rfr=4%
    # expected CAPM return = 4 + 1.2*(15-4) = 4 + 13.2 = 17.2%
    # alpha = 20 - 17.2 = 2.8%
    alpha = compute_jensen_alpha(
        stock_return=20.0, beta=1.2, market_return=15.0, risk_free_rate=4.0
    )
    assert abs(alpha - 2.8) < 0.01

def test_compute_annualized_return():
    # 3-year total return of 50% -> annualized ~14.47%
    ret = compute_annualized_return(total_return_pct=50.0, years=3)
    assert abs(ret - 14.47) < 0.1

def test_compute_volatility():
    monthly_returns = pd.Series([0.02, -0.01, 0.03, -0.02, 0.01])
    vol = compute_volatility(monthly_returns)
    expected = monthly_returns.std() * (12 ** 0.5) * 100
    assert abs(vol - expected) < 0.01
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_portfolio_engine.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write app/portfolio_engine.py**

```python
import numpy as np
import pandas as pd
from scipy import stats

from app.models import LifeStage, LifeStageProfile, StockMetrics, LIFE_STAGE_PROFILES


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
    mdd = float(drawdown.min())
    return round(mdd, 2)


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
    return round(float(monthly_returns.std() * (12 ** 0.5) * 100), 4)


def compute_all_metrics(
    tickers: list[str],
    prices_df: pd.DataFrame,
    spy_prices: pd.Series,
    risk_free_rate: float,
    spy_annualized_return: float,
    company_info: dict[str, dict],   # ticker -> {company_name, sector}
    years: int = 3,
) -> list[StockMetrics]:
    spy_returns = spy_prices.pct_change().dropna()
    results = []

    for ticker in tickers:
        if ticker not in prices_df.columns:
            continue
        series = prices_df[ticker].dropna()
        if len(series) < 12:
            continue

        monthly_returns = series.pct_change().dropna()
        total_return_pct = (series.iloc[-1] / series.iloc[0] - 1) * 100
        ann_return = compute_annualized_return(total_return_pct, years)
        beta = compute_beta(monthly_returns, spy_returns)
        vol = compute_volatility(monthly_returns)
        mdd = compute_max_drawdown(series)
        alpha = compute_jensen_alpha(ann_return, beta, spy_annualized_return, risk_free_rate)

        info = company_info.get(ticker, {})
        results.append(StockMetrics(
            ticker=ticker,
            company_name=info.get("company_name", ticker),
            sector=info.get("sector", "Unknown"),
            jensen_alpha=alpha,
            beta=beta,
            annualized_return=ann_return,
            volatility=vol,
            max_drawdown=mdd,
        ))

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
            s for s in post_beta
            if s.max_drawdown >= -profile.max_drawdown_limit
        ]
    return post_drawdown, len(post_beta), len(post_drawdown)


def rank_by_alpha(screened: list[StockMetrics]) -> list[StockMetrics]:
    return sorted(screened, key=lambda s: s.jensen_alpha, reverse=True)


def apply_sector_cap(
    ranked: list[StockMetrics], top_n: int = 15, max_per_sector: int = 3
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_portfolio_engine.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/portfolio_engine.py tests/test_portfolio_engine.py
git commit -m "feat: add portfolio metrics engine with beta, drawdown, Jensen's alpha"
```

---

## Task 5: Claude LLM Agent (Steps 4–7 of Prompt)

**Files:**
- Create: `app/llm_agent.py`

Note: No unit test for the LLM call itself — it's an integration boundary. The API response is validated by Pydantic, which serves as the contract test.

- [ ] **Step 1: Write app/llm_agent.py**

```python
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from app.models import (
    LifeStage, LifeStageProfile, StockMetrics, PortfolioResponse,
    LIFE_STAGE_PROFILES
)

load_dotenv()

SYSTEM_PROMPT_PATH = Path("portfolio_construction_prompt.md")
_SYSTEM_PROMPT: str | None = None


def _get_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        _SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text()
    return _SYSTEM_PROMPT


def _build_user_message(
    life_stage: LifeStage,
    profile: LifeStageProfile,
    universe_size: int,
    post_beta_count: int,
    post_drawdown_count: int,
    top_15: list[StockMetrics],
    spy_return: float,
    risk_free_rate: float,
) -> str:
    candidates_json = json.dumps(
        [s.model_dump() for s in top_15], indent=2
    )
    drawdown_limit = (
        "Unconstrained"
        if profile.max_drawdown_limit is None
        else f"{profile.max_drawdown_limit}%"
    )
    return f"""
You are constructing a portfolio for an investor in the **{life_stage.value}** life stage.

## Pre-Computed Screening Results (Steps 1–3 already completed by Python)

- S&P 500 universe size: {universe_size} stocks
- After beta cap filter (≤ {profile.beta_cap}): {post_beta_count} stocks
- After max drawdown filter ({drawdown_limit}): {post_drawdown_count} stocks
- SPY annualized return (3-year): {spy_return:.2f}%
- Risk-free rate used: {risk_free_rate:.2f}%

## Top 15 Candidates (ranked by Jensen's Alpha, sector cap ≤ 3 applied):

```json
{candidates_json}
```

## Your Task

Using the life-stage parameters:
- Beta cap: {profile.beta_cap}
- Max drawdown limit: {drawdown_limit}
- Minimum alpha target: +{profile.min_alpha_target_pct}% over S&P 500
- Weighting preference: {profile.volatility_preference}

Please execute **Steps 4 through 7** of the portfolio construction protocol:
- STEP 4: Select final 10 stocks and assign portfolio weights
- STEP 5: Compute portfolio-level metrics
- STEP 6: Self-verification checklist
- STEP 7: Per-stock rationale, portfolio role, and key risk

Respond ONLY with the structured JSON output format defined in the protocol.
The JSON must be valid and parseable. Do not include any text outside the JSON block.
"""


def build_portfolio_with_llm(
    life_stage: LifeStage,
    universe_size: int,
    post_beta_count: int,
    post_drawdown_count: int,
    top_15: list[StockMetrics],
    spy_return: float,
    risk_free_rate: float,
) -> PortfolioResponse:
    profile = LIFE_STAGE_PROFILES[life_stage]
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_message = _build_user_message(
        life_stage, profile, universe_size, post_beta_count,
        post_drawdown_count, top_15, spy_return, risk_free_rate
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_get_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        ).strip()

    data = json.loads(raw_text)
    return PortfolioResponse.model_validate(data)
```

- [ ] **Step 2: Verify file is importable**

```bash
python -c "from app.llm_agent import build_portfolio_with_llm; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/llm_agent.py
git commit -m "feat: add Claude LLM agent for portfolio steps 4-7"
```

---

## Task 6: FastAPI App & Endpoints

**Files:**
- Create: `app/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models import LifeStage

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_portfolio_invalid_life_stage():
    response = client.post("/portfolio", json={"life_stage": "Invalid Stage"})
    assert response.status_code == 422


def test_portfolio_valid_request_mocked(mock_portfolio_response):
    with patch("app.main.run_portfolio_pipeline") as mock_run:
        mock_run.return_value = mock_portfolio_response
        response = client.post(
            "/portfolio", json={"life_stage": "Growth"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "portfolio" in data
    assert len(data["portfolio"]) == 10


@pytest.fixture
def mock_portfolio_response():
    from app.models import (
        PortfolioResponse, ScreeningSummary, PortfolioMetrics,
        Verification, DataProvenance, PortfolioStock
    )
    stock = PortfolioStock(
        rank=1, ticker="AAPL", company_name="Apple Inc.",
        sector="Information Technology", weight_pct=10.0,
        jensen_alpha=8.0, beta=1.1, annualized_return=20.0,
        volatility=18.0, max_drawdown=-22.0,
        rationale="Strong alpha.", portfolio_role="Core tech.", key_risk="Valuation."
    )
    portfolio = [stock] * 10
    # fix ranks
    for i, s in enumerate(portfolio, 1):
        s = s.model_copy(update={"rank": i, "ticker": f"T{i}"})
        portfolio[i - 1] = s

    return PortfolioResponse(
        investor_profile={"life_stage": "Growth", "beta_cap": 1.2,
                          "max_drawdown_limit": "25%", "min_alpha_target_pct": 4.0},
        screening_summary=ScreeningSummary(
            universe_size=503, post_beta_filter_count=320,
            post_drawdown_filter_count=280, risk_free_rate_used=4.3,
            spy_annualized_return=12.0, top_15_candidates=[]
        ),
        portfolio=portfolio,
        portfolio_metrics=PortfolioMetrics(
            weighted_avg_beta=1.05, weighted_avg_alpha_pct=6.5,
            expected_annualized_return_pct=18.5, portfolio_max_drawdown_pct=-20.0,
            sharpe_ratio=1.2, total_weight_pct=100.0, alpha_target_met=True
        ),
        verification=Verification(
            stock_count_ok=True, sp500_membership_ok=True, beta_cap_ok=True,
            drawdown_constraint_ok=True, sector_concentration_ok=True,
            alpha_target_ok=True, weights_sum_ok=True, all_checks_passed=True,
            corrections_made="None"
        ),
        data_provenance=DataProvenance(
            data_source="yfinance", lookback_period="3 years monthly",
            benchmark="SPY", risk_free_rate=4.3, data_as_of="2026-05-14"
        ),
        warnings=[]
    )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_api.py::test_health_check tests/test_api.py::test_portfolio_invalid_life_stage -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write app/main.py**

```python
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.data_fetcher import (
    get_sp500_tickers, get_monthly_prices,
    get_spy_annualized_return, get_risk_free_rate
)
from app.models import (
    LifeStage, PortfolioRequest, PortfolioResponse, LIFE_STAGE_PROFILES
)
from app.portfolio_engine import (
    compute_all_metrics, screen_universe, rank_by_alpha, apply_sector_cap
)
from app.llm_agent import build_portfolio_with_llm

load_dotenv()

app = FastAPI(
    title="Portfolio Construction API",
    description="Jensen's Alpha-maximizing S&P 500 portfolio tailored to investor life stage",
    version="1.0.0",
)

static_path = Path("static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", response_class=FileResponse)
def read_root():
    return FileResponse("static/index.html")


@app.get("/life-stages")
def list_life_stages():
    return [stage.value for stage in LifeStage]


@app.post("/portfolio", response_model=PortfolioResponse)
def construct_portfolio(request: PortfolioRequest):
    return run_portfolio_pipeline(request.life_stage)


def run_portfolio_pipeline(life_stage: LifeStage) -> PortfolioResponse:
    """Orchestrates data fetch → screening → LLM construction."""
    profile = LIFE_STAGE_PROFILES[life_stage]

    # 1. Fetch data
    tickers = get_sp500_tickers()
    risk_free_rate = get_risk_free_rate()
    spy_return = get_spy_annualized_return(years=3)

    prices_df = get_monthly_prices(tickers, years=3)

    # Build company_info from S&P500 Wikipedia table
    import pandas as pd
    table = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", header=0
    )[0]
    company_info = {
        row["Symbol"].replace(".", "-"): {
            "company_name": row["Security"],
            "sector": row["GICS Sector"],
        }
        for _, row in table.iterrows()
    }

    spy_prices = prices_df.get("SPY")
    if spy_prices is None:
        spy_data = get_monthly_prices(["SPY"], years=3)
        spy_prices = spy_data["SPY"]

    # 2. Compute metrics
    all_metrics = compute_all_metrics(
        tickers=tickers,
        prices_df=prices_df,
        spy_prices=spy_prices,
        risk_free_rate=risk_free_rate,
        spy_annualized_return=spy_return,
        company_info=company_info,
    )

    # 3. Screen + rank + sector-diversify
    screened, post_beta, post_drawdown = screen_universe(all_metrics, profile)
    ranked = rank_by_alpha(screened)
    top_15 = apply_sector_cap(ranked, top_n=15, max_per_sector=3)

    if len(top_15) < 10:
        # Relax sector cap to 4 per sector
        top_15 = apply_sector_cap(ranked, top_n=15, max_per_sector=4)

    if len(top_15) < 10:
        raise HTTPException(
            status_code=422,
            detail=f"Only {len(top_15)} candidates passed filters for {life_stage.value}. Try a less restrictive life stage."
        )

    # 4. Claude: steps 4–7 (weighting, metrics, verification, rationale)
    portfolio_response = build_portfolio_with_llm(
        life_stage=life_stage,
        universe_size=len(tickers),
        post_beta_count=post_beta,
        post_drawdown_count=post_drawdown,
        top_15=top_15,
        spy_return=spy_return,
        risk_free_rate=risk_free_rate,
    )
    return portfolio_response
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_api.py::test_health_check tests/test_api.py::test_portfolio_invalid_life_stage tests/test_api.py::test_portfolio_valid_request_mocked -v
```

Expected: All 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: add FastAPI endpoints with portfolio pipeline"
```

---

## Task 7: HTML Frontend

**Files:**
- Create: `static/index.html`

- [ ] **Step 1: Write static/index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Portfolio Constructor</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
    h1 { font-size: 1.8rem; color: #38bdf8; margin-bottom: 0.25rem; }
    .subtitle { color: #64748b; margin-bottom: 2rem; font-size: 0.9rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    label { display: block; margin-bottom: 0.5rem; font-weight: 600; color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
    select { width: 100%; max-width: 400px; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 1rem; }
    button { margin-top: 1rem; padding: 0.75rem 2rem; background: #0ea5e9; color: white; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
    button:hover { background: #38bdf8; }
    button:disabled { background: #334155; cursor: not-allowed; }
    .metrics-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .metric { background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; }
    .metric-value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; }
    .metric-label { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value.green { color: #4ade80; }
    .metric-value.red { color: #f87171; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th { text-align: left; padding: 0.6rem 0.8rem; color: #64748b; border-bottom: 1px solid #334155; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }
    td { padding: 0.8rem; border-bottom: 1px solid #1e293b; vertical-align: top; }
    tr:hover td { background: #1e293b; }
    .ticker { font-weight: 700; color: #38bdf8; }
    .weight-bar { display: inline-block; height: 6px; background: #0ea5e9; border-radius: 3px; margin-left: 8px; vertical-align: middle; }
    .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: #1e3a5f; color: #93c5fd; }
    .alpha-pos { color: #4ade80; }
    .alpha-neg { color: #f87171; }
    .warning { background: #422006; border-left: 3px solid #f97316; padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.85rem; color: #fed7aa; }
    .check { color: #4ade80; }
    .cross { color: #f87171; }
    #loading { display: none; text-align: center; padding: 3rem; color: #64748b; }
    #loading .spinner { font-size: 2rem; animation: spin 1s linear infinite; display: inline-block; margin-bottom: 1rem; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    #error { display: none; background: #450a0a; border-left: 3px solid #f87171; padding: 1rem; border-radius: 4px; color: #fca5a5; margin-bottom: 1rem; }
    #results { display: none; }
    .rationale { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
    .risk { font-size: 0.78rem; color: #f97316; margin-top: 0.15rem; }
  </style>
</head>
<body>
  <h1>Portfolio Constructor</h1>
  <p class="subtitle">Jensen's Alpha-maximizing S&P 500 portfolios tailored to your investor life stage</p>

  <div class="card">
    <label for="lifeStage">Investor Life Stage</label>
    <select id="lifeStage">
      <option value="Early Investor">Early Investor (&lt; 5 years working capital)</option>
      <option value="Accelerate">Accelerate (up to 10 years)</option>
      <option value="Growth" selected>Growth (up to 20 years)</option>
      <option value="Protect">Protect (up to 30 years)</option>
      <option value="Retirement">Retirement (beyond 30 years)</option>
    </select>
    <button id="buildBtn" onclick="buildPortfolio()">Build Portfolio</button>
  </div>

  <div id="loading">
    <div class="spinner">⚙</div>
    <div>Fetching S&P 500 data and constructing portfolio…</div>
    <div style="font-size:0.8rem; margin-top:0.5rem; color:#475569">This may take 30–60 seconds on first run</div>
  </div>

  <div id="error"></div>
  <div id="results"></div>

  <script>
    async function buildPortfolio() {
      const lifeStage = document.getElementById("lifeStage").value;
      const btn = document.getElementById("buildBtn");
      btn.disabled = true;
      document.getElementById("loading").style.display = "block";
      document.getElementById("results").style.display = "none";
      document.getElementById("error").style.display = "none";

      try {
        const res = await fetch("/portfolio", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({life_stage: lifeStage})
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Request failed");
        }

        const data = await res.json();
        renderResults(data);
      } catch (e) {
        const errEl = document.getElementById("error");
        errEl.textContent = "Error: " + e.message;
        errEl.style.display = "block";
      } finally {
        btn.disabled = false;
        document.getElementById("loading").style.display = "none";
      }
    }

    function renderResults(data) {
      const el = document.getElementById("results");
      const m = data.portfolio_metrics;
      const v = data.verification;
      const profile = data.investor_profile;

      const checks = [
        ["stock_count_ok","10 stocks selected"],
        ["sp500_membership_ok","All S&P 500 members"],
        ["beta_cap_ok","Beta cap satisfied"],
        ["drawdown_constraint_ok","Drawdown limit met"],
        ["sector_concentration_ok","Sector concentration OK"],
        ["alpha_target_ok","Alpha target met"],
        ["weights_sum_ok","Weights sum to 100%"],
      ].map(([k,label]) => `<div>${v[k] ? '<span class="check">✓</span>' : '<span class="cross">✗</span>'} ${label}</div>`).join("");

      const warnings = data.warnings?.length
        ? data.warnings.map(w => `<div class="warning">⚠ ${w}</div>`).join("")
        : "";

      const rows = data.portfolio.map(s => `
        <tr>
          <td><span class="ticker">${s.ticker}</span> <span class="tag">${s.sector.split(" ").slice(-1)[0]}</span>
            <div class="rationale">${s.rationale}</div>
            <div class="risk">⚠ ${s.key_risk}</div>
          </td>
          <td>${s.company_name}</td>
          <td class="${s.jensen_alpha >= 0 ? 'alpha-pos' : 'alpha-neg'}">${s.jensen_alpha.toFixed(1)}%</td>
          <td>${s.beta.toFixed(2)}</td>
          <td>${s.annualized_return.toFixed(1)}%</td>
          <td>${s.max_drawdown.toFixed(1)}%</td>
          <td>${s.weight_pct.toFixed(1)}%<span class="weight-bar" style="width:${s.weight_pct * 2}px"></span></td>
        </tr>`).join("");

      el.innerHTML = `
        ${warnings}
        <div class="card">
          <h2 style="margin-bottom:1rem;color:#94a3b8">Portfolio Metrics — ${profile.life_stage}</h2>
          <div class="metrics-grid">
            <div class="metric"><div class="metric-value green">+${m.weighted_avg_alpha_pct.toFixed(1)}%</div><div class="metric-label">Jensen's Alpha</div></div>
            <div class="metric"><div class="metric-value">${m.expected_annualized_return_pct.toFixed(1)}%</div><div class="metric-label">Expected Return</div></div>
            <div class="metric"><div class="metric-value">${m.weighted_avg_beta.toFixed(2)}</div><div class="metric-label">Portfolio Beta</div></div>
            <div class="metric"><div class="metric-value red">${m.portfolio_max_drawdown_pct.toFixed(1)}%</div><div class="metric-label">Max Drawdown</div></div>
            <div class="metric"><div class="metric-value">${m.sharpe_ratio.toFixed(2)}</div><div class="metric-label">Sharpe Ratio</div></div>
            <div class="metric"><div class="metric-value ${m.alpha_target_met ? 'green' : 'red'}">${m.alpha_target_met ? '✓' : '✗'}</div><div class="metric-label">+4% Target Met</div></div>
          </div>
        </div>
        <div class="card">
          <h2 style="margin-bottom:1rem;color:#94a3b8">Portfolio Holdings</h2>
          <table>
            <thead><tr><th>Stock</th><th>Company</th><th>α Alpha</th><th>Beta</th><th>Return</th><th>Max DD</th><th>Weight</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <div class="card">
          <h2 style="margin-bottom:0.75rem;color:#94a3b8">Verification</h2>
          ${checks}
          ${v.corrections_made !== "None" ? `<div style="margin-top:0.75rem;color:#f97316;font-size:0.85rem">Corrections: ${v.corrections_made}</div>` : ""}
        </div>
        <div class="card" style="font-size:0.75rem;color:#475569">
          Data: ${data.data_provenance.data_source} · ${data.data_provenance.lookback_period} · 
          Benchmark: ${data.data_provenance.benchmark} · Risk-free rate: ${data.data_provenance.risk_free_rate}% · 
          As of: ${data.data_provenance.data_as_of}
          <br><br>
          <em>For analytical purposes only. Not financial advice.</em>
        </div>`;

      el.style.display = "block";
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify file exists**

```bash
ls -la static/index.html
```

Expected: File present.

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: add portfolio frontend with life-stage dropdown"
```

---

## Task 8: End-to-End Smoke Test

- [ ] **Step 1: Create .env with your API key**

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 2: Start the server**

```bash
uvicorn app.main:app --reload --port 8000
```

Expected: `INFO: Application startup complete.`

- [ ] **Step 3: Test health endpoint**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","version":"1.0.0"}`

- [ ] **Step 4: Test portfolio endpoint (Growth stage)**

```bash
curl -X POST http://localhost:8000/portfolio \
  -H "Content-Type: application/json" \
  -d '{"life_stage": "Growth"}' | python -m json.tool | head -50
```

Expected: JSON with `portfolio` array of 10 stocks, `portfolio_metrics.alpha_target_met: true`.

- [ ] **Step 5: Open browser**

Navigate to `http://localhost:8000/static/index.html`, select a life stage, click Build Portfolio, verify results render.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --ignore=tests/test_data_fetcher.py
```

Expected: All non-integration tests pass. (`test_data_fetcher.py` skipped to avoid slow network calls in CI.)

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "feat: complete portfolio construction app v1"
```

---

## Self-Review Against Spec

| Requirement | Task | Status |
|---|---|---|
| FastAPI-based app | Task 6 | ✅ |
| Pydantic structure definitions | Task 2 | ✅ |
| 10 stocks from S&P 500 | Task 5 + LLM step 4 | ✅ |
| Maximize Jensen's Alpha | Task 4 + Task 5 | ✅ |
| Life-stage dropdown (5 stages) | Task 2 + Task 7 | ✅ |
| Risk/volatility profile per stage | Task 2 (LIFE_STAGE_PROFILES) | ✅ |
| Minimize max drawdown for Retirement | Task 5 screen_universe | ✅ |
| +4% alpha over S&P 500 target | Task 5 + LLM verification | ✅ |
| Prompt from portfolio_construction_prompt.md | Task 5 (llm_agent uses it as system prompt) | ✅ |
| meta_prompt.md criteria (all 9) | Prompt already written & scored | ✅ |
