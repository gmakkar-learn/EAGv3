import json
from datetime import date
from pathlib import Path
from typing import Any

import yfinance as yf
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.data_fetcher import (
    get_monthly_prices,
    get_risk_free_rate,
    get_sp500_company_info,
    get_sp500_tickers,
    get_spy_annualized_return,
)
from app.llm_agent import build_portfolio_with_llm
from app.models import (
    LIFE_STAGE_PROFILES,
    LifeStage,
    PortfolioRequest,
    PortfolioResponse,
    StockMetrics,
)
from app.portfolio_engine import (
    apply_sector_cap,
    compute_all_metrics,
    rank_by_alpha,
    screen_universe,
)

load_dotenv()

app = FastAPI(
    title="Portfolio Construction API",
    description="Jensen's Alpha-maximizing S&P 500 portfolio tailored to investor life stage",
    version="1.0.0",
)

static_path = Path("static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

CACHE_DIR = Path(".cache")

# --- In-memory caches (live for the server process lifetime) ---
# Keyed by life_stage.value → PortfolioResponse
_portfolio_mem: dict[str, PortfolioResponse] = {}

# Computed once per server session; all life stages share the same market data
_metrics_mem: dict[str, Any] | None = None  # {metrics, rfr, spy_return, universe_size}


# --- Disk cache helpers (survive server restarts, keyed by date) ---

def _today() -> str:
    return date.today().isoformat()


def _portfolio_disk_path(life_stage: LifeStage) -> Path:
    slug = life_stage.value.lower().replace(" ", "_")
    return CACHE_DIR / f"portfolio_{slug}_{_today()}.json"


def _load_portfolio_disk(life_stage: LifeStage) -> PortfolioResponse | None:
    path = _portfolio_disk_path(life_stage)
    if path.exists():
        try:
            return PortfolioResponse.model_validate_json(path.read_text())
        except Exception:
            pass
    return None


def _save_portfolio_disk(life_stage: LifeStage, response: PortfolioResponse) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _portfolio_disk_path(life_stage).write_text(response.model_dump_json(indent=2))


# --- Routes ---

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", response_class=FileResponse)
def read_root():
    return FileResponse("static/index.html")


@app.get("/life-stages")
def list_life_stages():
    return [stage.value for stage in LifeStage]


@app.get("/cache/status")
def cache_status():
    """Show which life stages have been computed and cached."""
    disk_cached = []
    for stage in LifeStage:
        if _portfolio_disk_path(stage).exists():
            disk_cached.append(stage.value)
    return {
        "memory_cached": list(_portfolio_mem.keys()),
        "disk_cached": disk_cached,
        "metrics_computed": _metrics_mem is not None,
        "cache_date": _today(),
    }


@app.delete("/cache")
def clear_cache():
    """Invalidate all in-memory and today's disk caches."""
    global _portfolio_mem, _metrics_mem
    _portfolio_mem = {}
    _metrics_mem = None
    removed = 0
    for stage in LifeStage:
        p = _portfolio_disk_path(stage)
        if p.exists():
            p.unlink()
            removed += 1
    return {"cleared_disk_files": removed, "message": "Cache cleared"}


@app.post("/portfolio", response_model=PortfolioResponse)
def construct_portfolio(request: PortfolioRequest):
    return run_portfolio_pipeline(request.life_stage)


def run_portfolio_pipeline(life_stage: LifeStage) -> PortfolioResponse:
    global _portfolio_mem, _metrics_mem

    # ── Layer 1: in-memory cache (sub-millisecond) ──────────────────────────
    if life_stage.value in _portfolio_mem:
        return _portfolio_mem[life_stage.value]

    # ── Layer 2: disk cache (survives restarts, refreshes daily) ────────────
    from_disk = _load_portfolio_disk(life_stage)
    if from_disk is not None:
        _portfolio_mem[life_stage.value] = from_disk  # promote to memory
        return from_disk

    # ── Layer 3: compute metrics (once per session, all life stages share) ──
    profile = LIFE_STAGE_PROFILES[life_stage]

    if _metrics_mem is None:
        tickers = get_sp500_tickers()
        risk_free_rate = get_risk_free_rate()
        spy_return = get_spy_annualized_return(years=3)
        company_info = get_sp500_company_info()

        prices_df = get_monthly_prices(tickers, years=3)
        spy_prices = yf.Ticker("SPY").history(period="3y", interval="1mo")["Close"]

        all_metrics = compute_all_metrics(
            tickers=tickers,
            prices_df=prices_df,
            spy_prices=spy_prices,
            risk_free_rate=risk_free_rate,
            spy_annualized_return=spy_return,
            company_info=company_info,
        )
        _metrics_mem = {
            "metrics": all_metrics,
            "rfr": risk_free_rate,
            "spy_return": spy_return,
            "universe_size": len(tickers),
        }

    all_metrics: list[StockMetrics] = _metrics_mem["metrics"]
    risk_free_rate: float = _metrics_mem["rfr"]
    spy_return: float = _metrics_mem["spy_return"]
    universe_size: int = _metrics_mem["universe_size"]

    # ── Screen + rank + sector-diversify (fast, per life stage) ─────────────
    screened, post_beta, post_drawdown = screen_universe(all_metrics, profile)
    ranked = rank_by_alpha(screened)
    top_15 = apply_sector_cap(ranked, top_n=15, max_per_sector=3)

    if len(top_15) < 10:
        top_15 = apply_sector_cap(ranked, top_n=15, max_per_sector=4)

    if len(top_15) < 10:
        raise HTTPException(
            status_code=422,
            detail=f"Only {len(top_15)} candidates passed filters for {life_stage.value}. "
            "Try a less restrictive life stage.",
        )

    # ── Call Claude (once per life stage per day) ────────────────────────────
    result = build_portfolio_with_llm(
        life_stage=life_stage,
        universe_size=universe_size,
        post_beta_count=post_beta,
        post_drawdown_count=post_drawdown,
        top_15=top_15,
        spy_return=spy_return,
        risk_free_rate=risk_free_rate,
    )

    # ── Persist to both caches ───────────────────────────────────────────────
    _portfolio_mem[life_stage.value] = result
    _save_portfolio_to_disk(life_stage, result)

    return result


def _save_portfolio_to_disk(life_stage: LifeStage, response: PortfolioResponse) -> None:
    _save_portfolio_disk(life_stage, response)
