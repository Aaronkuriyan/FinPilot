from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import numpy as np


@dataclass
class RecurringCandidate:
    merchant: str
    recurrence: str
    average_amount: Decimal
    amount_stddev: Decimal
    occurrence_count: int
    last_charge_date: date
    next_due_date: date
    confidence: Decimal
    active: bool


class RecurringDetector:

    INTERVALS = {
        "weekly": (7, 2),
        "monthly": (30, 5),
        "yearly": (365, 20),
    }

    def detect(self, transactions) -> list[RecurringCandidate]:
        grouped = defaultdict(list)

        for transaction in transactions:
            merchant = self.normalize_merchant(
                transaction.merchant
                or transaction.description
                or ""
            )

            if not merchant:
                continue

            if transaction.transaction_type.value != "expense":
                continue

            grouped[merchant].append(transaction)

        candidates = []

        for merchant, txns in grouped.items():
            if len(txns) < 3:
                continue

            txns.sort(
                key=lambda transaction: transaction.transaction_date
            )

            dates = [
                transaction.transaction_date
                for transaction in txns
            ]

            amounts = np.array(
                [
                    float(transaction.amount)
                    for transaction in txns
                ],
                dtype=float,
            )

            interval = self._detect_interval(dates)

            if not interval:
                continue

            recurrence, interval_days, interval_tolerance = interval

            amount_mean = float(np.mean(amounts))
            amount_std = float(np.std(amounts))

            if amount_mean <= 0:
                continue

            # Relative amount variation.
            coefficient_variation = (
                amount_std / amount_mean
            )

            # Subscription charges can vary somewhat,
            # but highly variable merchants are less likely recurring.
            if coefficient_variation > 0.20:
                continue

            interval_score = self._interval_score(
                dates,
                interval_days,
                interval_tolerance,
            )

            amount_score = max(
                0.0,
                1.0 - coefficient_variation / 0.20,
            )

            occurrence_score = min(
                1.0,
                len(txns) / 6,
            )

            confidence = (
                0.45 * interval_score
                + 0.40 * amount_score
                + 0.15 * occurrence_score
            )

            last_date = dates[-1]

            next_due = last_date + timedelta(
                days=interval_days
            )

            active = (
                date.today() - last_date
                <= timedelta(days=interval_days * 2)
            )

            candidates.append(
                RecurringCandidate(
                    merchant=merchant,
                    recurrence=recurrence,
                    average_amount=Decimal(
                        str(round(amount_mean, 2))
                    ),
                    amount_stddev=Decimal(
                        str(round(amount_std, 2))
                    ),
                    occurrence_count=len(txns),
                    last_charge_date=last_date,
                    next_due_date=next_due,
                    confidence=Decimal(
                        str(round(confidence, 4))
                    ),
                    active=active,
                )
            )

        return sorted(
            candidates,
            key=lambda item: item.confidence,
            reverse=True,
        )

    def _detect_interval(self, dates):
        intervals = [
            (dates[index] - dates[index - 1]).days
            for index in range(1, len(dates))
        ]

        if not intervals:
            return None

        median_interval = float(
            np.median(intervals)
        )

        best = None
        best_error = math.inf

        for recurrence, (
            expected,
            tolerance,
        ) in self.INTERVALS.items():
            error = abs(
                median_interval - expected
            )

            if error <= tolerance and error < best_error:
                best = (
                    recurrence,
                    expected,
                    tolerance,
                )
                best_error = error

        return best

    @staticmethod
    def _interval_score(
        dates,
        expected,
        tolerance,
    ):
        intervals = [
            (dates[index] - dates[index - 1]).days
            for index in range(1, len(dates))
        ]

        if not intervals:
            return 0.0

        errors = [
            abs(interval - expected)
            for interval in intervals
        ]

        mean_error = float(
            np.mean(errors)
        )

        return max(
            0.0,
            1.0 - mean_error / tolerance,
        )

    @staticmethod
    def normalize_merchant(value: str) -> str:
        value = value.lower()

        value = re.sub(
            r"\b(upi|pos|neft|imps|rtgs)\b",
            "",
            value,
        )

        value = re.sub(
            r"\b\d{4,}\b",
            "",
            value,
        )

        value = re.sub(
            r"[^a-z0-9 ]",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()