"""Analysis engine prompt templates loader.

Each .md file defines a domain-specific analysis methodology.
The loader reads templates on demand for injection into system prompts.
"""

import os
from typing import Optional

_PROMPT_DIR = os.path.dirname(__file__)
_CACHE: dict[str, str] = {}


def load_prompt(engine_name: str) -> Optional[str]:
    """Load a prompt template by engine name (without .md extension).

    Returns the template text, or None if the file doesn't exist.
    Results are cached in memory after first load.
    """
    if engine_name in _CACHE:
        return _CACHE[engine_name]

    filepath = os.path.join(_PROMPT_DIR, f"{engine_name}.md")
    if not os.path.exists(filepath):
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        template = f.read().strip()

    _CACHE[engine_name] = template
    return template


def list_engines() -> list[str]:
    """List available engine names."""
    engines = []
    for fname in os.listdir(_PROMPT_DIR):
        if fname.endswith(".md"):
            engines.append(fname[:-3])
    return sorted(engines)


# Mapping: user intent keywords → engine name
INTENT_ENGINE_MAP = {
    "财报": "financials",
    "业绩": "financials",
    "利润": "financials",
    "营收": "financials",
    "估值": "valuation",
    "贵不贵": "valuation",
    "便宜": "valuation",
    "盘面": "radar",
    "资金": "radar",
    "筹码": "radar",
    "持仓诊断": "portfolio_diagnosis",
    "诊断": "portfolio_diagnosis",
    "组合": "portfolio_diagnosis",
}


def detect_engine(user_message: str) -> Optional[str]:
    """Detect which analysis engine to use based on user message keywords.

    Priority:
    1. Exact keyword match → specific engine (financials/valuation/radar/portfolio_diagnosis)
    2. Broad stock query (contains stock-related terms but no specific engine keyword) → "combined"
    3. No stock intent → None
    """
    # 1. Exact keyword match
    for keyword, engine in INTENT_ENGINE_MAP.items():
        if keyword in user_message:
            return engine

    # 2. Broad stock query fallback: user likely wants multi-dimensional analysis
    broad_keywords = ["看看", "分析", "这只", "那个", "走势", "行情", "怎么", "如何", "怎么样"]
    stock_indicators = ["股票", "个股", "代码", "自选"]
    has_broad = any(kw in user_message for kw in broad_keywords)
    has_stock = any(kw in user_message for kw in stock_indicators)
    if has_broad:
        return "combined"

    return None
