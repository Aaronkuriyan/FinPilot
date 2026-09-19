from __future__ import annotations

import re
from decimal import Decimal

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings


STANDARD_CATEGORIES = [
    "Housing",
    "Utilities",
    "Groceries",
    "Dining",
    "Subscriptions",
    "Transportation",
    "Healthcare",
    "Entertainment",
    "Miscellaneous",
]


CATEGORY_RULES: dict[str, list[str]] = {
    "Housing": [
        r"\brent\b",
        r"\bhousing\b",
        r"\bapartment\b",
        r"\bmortgage\b",
        r"\bproperty\b",
        r"\blandlord\b",
    ],
    "Utilities": [
        r"\belectric\b",
        r"\belectricity\b",
        r"\bwater bill\b",
        r"\binternet\b",
        r"\bbroadband\b",
        r"\bwifi\b",
        r"\bairtel\b",
        r"\bjio\b",
        r"\bvodafone\b",
        r"\bvi\b",
        r"\bmobile bill\b",
    ],
    "Groceries": [
        r"\bgrocery\b",
        r"\bgroceries\b",
        r"\bsupermarket\b",
        r"\bmart\b",
        r"\bwhole foods\b",
        r"\blulu\b",
        r"\bbigbasket\b",
        r"\bblinkit\b",
        r"\bzepto\b",
        r"\bswiggy instamart\b",
    ],
    "Dining": [
        r"\brestaurant\b",
        r"\bcafe\b",
        r"\bcoffee\b",
        r"\bpizza\b",
        r"\bburger\b",
        r"\bswiggy\b",
        r"\bzomato\b",
        r"\bkfc\b",
        r"\bmcdonald\b",
    ],
    "Subscriptions": [
        r"\bnetflix\b",
        r"\bspotify\b",
        r"\bprime video\b",
        r"\bamazon prime\b",
        r"\byoutube premium\b",
        r"\bdisney\b",
        r"\bhotstar\b",
        r"\bchatgpt\b",
        r"\bopenai\b",
        r"\bgithub\b",
    ],
    "Transportation": [
        r"\buber\b",
        r"\bol[aá]\b",
        r"\brapido\b",
        r"\bmetro\b",
        r"\bpetrol\b",
        r"\bdiesel\b",
        r"\bfuel\b",
        r"\bparking\b",
        r"\btoll\b",
    ],
    "Healthcare": [
        r"\bhospital\b",
        r"\bclinic\b",
        r"\bpharmacy\b",
        r"\bmedical\b",
        r"\bdoctor\b",
        r"\bapollo\b",
        r"\bmedplus\b",
    ],
    "Entertainment": [
        r"\bmovie\b",
        r"\bcinema\b",
        r"\bsteam\b",
        r"\bplaystation\b",
        r"\bxbox\b",
        r"\bgame\b",
        r"\bconcert\b",
    ],
}


class CategoryPrediction(BaseModel):
    category: str
    confidence: float


class Categorizer:
    def __init__(self):
        self.client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )

    async def categorize(
        self,
        merchant: str | None,
        description: str | None,
        amount: Decimal,
    ) -> CategoryPrediction:
        text = " ".join(
            part
            for part in [
                merchant,
                description,
            ]
            if part
        ).lower()

        deterministic = self._rule_match(text)

        if deterministic:
            return CategoryPrediction(
                category=deterministic,
                confidence=0.98,
            )

        if self.client:
            return await self._llm_fallback(
                merchant=merchant,
                description=description,
                amount=amount,
            )

        return CategoryPrediction(
            category="Miscellaneous",
            confidence=0.20,
        )

    @staticmethod
    def _rule_match(text: str) -> str | None:
        for category, patterns in CATEGORY_RULES.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return category

        return None

    async def _llm_fallback(
        self,
        merchant: str | None,
        description: str | None,
        amount: Decimal,
    ) -> CategoryPrediction:
        prompt = f"""
Classify this personal finance transaction.

Allowed categories:
{", ".join(STANDARD_CATEGORIES)}

Merchant:
{merchant or "Unknown"}

Description:
{description or "Unknown"}

Amount:
{amount}

Return exactly one category and confidence.
"""

        response = await self.client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify transactions. "
                        "Never provide investment advice."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format=CategoryPrediction,
        )

        parsed = response.choices[0].message.parsed

        if not parsed:
            return CategoryPrediction(
                category="Miscellaneous",
                confidence=0.10,
            )

        if parsed.category not in STANDARD_CATEGORIES:
            return CategoryPrediction(
                category="Miscellaneous",
                confidence=0.10,
            )

        parsed.confidence = max(
            0.0,
            min(1.0, parsed.confidence),
        )

        return parsed