from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from portfolio_rag_assistant.intent import IntentCatalog, load_intent_catalog

ROOT = Path(__file__).resolve().parents[1]
TRACKED_INTENT_CATALOG = ROOT / "config" / "intent-profiles.json"


@lru_cache(maxsize=1)
def tracked_intent_catalog() -> IntentCatalog:
    return load_intent_catalog(TRACKED_INTENT_CATALOG)
