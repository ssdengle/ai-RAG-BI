from __future__ import annotations

from apps.api.app.domain.retrieval import RetrievedChunk


RISK_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "regulatory": ("regulation", "regulatory", "compliance", "legal", "lawsuit", "litigation"),
    "financial": ("debt", "liquidity", "loss", "decline", "bankruptcy", "credit", "margin pressure"),
    "operational": ("supply chain", "disruption", "capacity", "operational", "production", "shortage"),
    "market": ("competition", "market share", "demand", "pricing pressure", "competitor"),
    "technology": ("cyber", "security", "technology", "obsolescence", "outage", "data breach"),
}

TREND_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "revenue_growth": ("revenue growth", "revenue increased", "sales growth", "top-line growth"),
    "market_expansion": ("market expansion", "geographic expansion", "new market", "market entry"),
    "innovation": ("innovation", "product launch", "r&d", "research and development", "new product"),
    "cost_optimization": ("cost reduction", "efficiency", "margin improvement", "cost optimization"),
    "digital_transformation": ("digital transformation", "automation", "cloud adoption", "ai adoption"),
}


def classify_risk_categories(text: str) -> list[str]:
    normalized = text.lower()
    categories = [
        category
        for category, keywords in RISK_CATEGORY_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return categories or ["general"]


def classify_trend_topics(text: str) -> list[str]:
    normalized = text.lower()
    topics = [
        topic
        for topic, keywords in TREND_TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return topics


def summarize_chunk_text(text: str, *, max_length: int = 160) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def build_risk_summary_text(category: str, chunk: RetrievedChunk) -> str:
    return f"{category.replace('_', ' ').title()} risk indicated in retrieved evidence."


def build_trend_summary_text(topic: str, chunk: RetrievedChunk) -> str:
    return f"{topic.replace('_', ' ').title()} trend indicated in retrieved evidence."
