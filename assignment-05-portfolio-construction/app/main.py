from pathlib import Path

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

    tickers = get_sp500_tickers()
    risk_free_rate = get_risk_free_rate()
    spy_return = get_spy_annualized_return(years=3)
    company_info = get_sp500_company_info()

    prices_df = get_monthly_prices(tickers, years=3)

    import yfinance as yf
    spy_hist = yf.Ticker("SPY").history(period="3y", interval="1mo")
    spy_prices = spy_hist["Close"]

    all_metrics = compute_all_metrics(
        tickers=tickers,
        prices_df=prices_df,
        spy_prices=spy_prices,
        risk_free_rate=risk_free_rate,
        spy_annualized_return=spy_return,
        company_info=company_info,
    )

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

    return build_portfolio_with_llm(
        life_stage=life_stage,
        universe_size=len(tickers),
        post_beta_count=post_beta,
        post_drawdown_count=post_drawdown,
        top_15=top_15,
        spy_return=spy_return,
        risk_free_rate=risk_free_rate,
    )
