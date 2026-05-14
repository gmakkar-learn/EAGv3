import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from app.models import (
    LIFE_STAGE_PROFILES,
    LifeStage,
    LifeStageProfile,
    PortfolioResponse,
    StockMetrics,
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
    candidates_json = json.dumps([s.model_dump() for s in top_15], indent=2)
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
        life_stage,
        profile,
        universe_size,
        post_beta_count,
        post_drawdown_count,
        top_15,
        spy_return,
        risk_free_rate,
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=_get_system_prompt(),
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    data = json.loads(raw_text)
    return PortfolioResponse.model_validate(data)
