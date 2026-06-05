"""Shared deterministic recruiter-question intent profiles."""

from portfolio_rag_assistant.intent.catalog import load_intent_catalog
from portfolio_rag_assistant.intent.profiles import (
    DEFAULT_INTENT_CATALOG,
    IntentCatalog,
    QUESTION_INTENT_PROFILES,
    QuestionIntent,
    QuestionIntentProfile,
    QuestionIntentProfileError,
    categories_for_intents,
    detect_question_intents,
    profile_for_intent,
    text_satisfies_intent_evidence,
)

__all__ = [
    "DEFAULT_INTENT_CATALOG",
    "IntentCatalog",
    "QUESTION_INTENT_PROFILES",
    "QuestionIntent",
    "QuestionIntentProfile",
    "QuestionIntentProfileError",
    "categories_for_intents",
    "detect_question_intents",
    "load_intent_catalog",
    "profile_for_intent",
    "text_satisfies_intent_evidence",
]
