from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import Budget
from app.models.category import Category
from app.models.subscription import Subscription
from app.models.transaction import (
    Transaction,
    TransactionType,
)


class AnalyticsService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_month_transactions(
        self,
        user_id,
        month: int,
        year: int,
    ):
        start = date(year, month, 1)

        last_day = monthrange(year, month)[1]

        end = date(
            year,
            month,
            last_day,
        )

        result = await self.db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start,
                Transaction.transaction_date <= end,
            )
            .order_by(Transaction.transaction_date)
        )

        return list(result.scalars().all())

    async def get_top_spending(
        self,
        user_id,
        month: int,
        year: int,
        limit: int = 10,
        category: str | None = None,
    ):
        query = (
            select(
                Category.name,
                func.sum(Transaction.amount).label("total"),
            )
            .join(
                Category,
                Transaction.category_id == Category.id,
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type
                == TransactionType.EXPENSE,
                func.extract(
                    "month",
                    Transaction.transaction_date,
                )
                == month,
                func.extract(
                    "year",
                    Transaction.transaction_date,
                )
                == year,
            )
            .group_by(Category.name)
            .order_by(
                func.sum(Transaction.amount).desc()
            )
            .limit(limit)
        )

        if category:
            query = query.where(
                Category.name == category
            )

        result = await self.db.execute(query)

        rows = result.all()

        total = sum(
            (Decimal(str(row.total)) for row in rows),
            Decimal("0"),
        )

        return [
            {
                "category": row.name,
                "amount": Decimal(str(row.total)),
                "percentage": (
                    Decimal(str(row.total))
                    / total
                    * Decimal("100")
                    if total
                    else Decimal("0")
                ),
            }
            for row in rows
        ]

    async def get_month_summary(
        self,
        user_id,
        month: int,
        year: int,
    ):
        transactions = await self.get_month_transactions(
            user_id,
            month,
            year,
        )

        income = sum(
            (
                transaction.amount
                for transaction in transactions
                if transaction.transaction_type
                == TransactionType.INCOME
            ),
            Decimal("0"),
        )

        expenses = sum(
            (
                transaction.amount
                for transaction in transactions
                if transaction.transaction_type
                == TransactionType.EXPENSE
            ),
            Decimal("0"),
        )

        net_cash_flow = income - expenses

        return {
            "month": month,
            "year": year,
            "income": income,
            "expenses": expenses,
            "net_cash_flow": net_cash_flow,
            "burn_rate": expenses,
            "transaction_count": len(transactions),
        }

    async def get_expense_increases(
        self,
        user_id,
        current_month: int,
        current_year: int,
        comparison_month: int,
        comparison_year: int,
    ):
        current = await self._category_totals(
            user_id,
            current_month,
            current_year,
        )

        comparison = await self._category_totals(
            user_id,
            comparison_month,
            comparison_year,
        )

        categories = (
            set(current.keys())
            | set(comparison.keys())
        )

        output = []

        for category in categories:
            current_amount = current.get(
                category,
                Decimal("0"),
            )

            comparison_amount = comparison.get(
                category,
                Decimal("0"),
            )

            absolute_change = (
                current_amount
                - comparison_amount
            )

            if comparison_amount != 0:
                percentage_change = (
                    absolute_change
                    / comparison_amount
                    * Decimal("100")
                )
            elif current_amount > 0:
                percentage_change = Decimal("100")
            else:
                percentage_change = Decimal("0")

            if absolute_change > 0:
                output.append(
                    {
                        "category": category,
                        "current_amount": current_amount,
                        "comparison_amount": comparison_amount,
                        "absolute_change": absolute_change,
                        "percentage_change": percentage_change,
                    }
                )

        output.sort(
            key=lambda item: item["absolute_change"],
            reverse=True,
        )

        return output

    async def detect_anomalies(
        self,
        user_id,
        month: int,
        year: int,
    ):
        transactions = await self.get_month_transactions(
            user_id,
            month,
            year,
        )

        expense_transactions = [
            transaction
            for transaction in transactions
            if transaction.transaction_type
            == TransactionType.EXPENSE
        ]

        if len(expense_transactions) < 4:
            return []

        amounts = np.array(
            [
                float(transaction.amount)
                for transaction in expense_transactions
            ],
            dtype=float,
        )

        mean = float(np.mean(amounts))
        std = float(np.std(amounts))

        if std == 0:
            return []

        anomalies = []

        for transaction in expense_transactions:
            z_score = (
                float(transaction.amount) - mean
            ) / std

            if abs(z_score) >= 2.5:
                anomalies.append(
                    {
                        "transaction_id": str(
                            transaction.id
                        ),
                        "date": transaction.transaction_date.isoformat(),
                        "merchant": transaction.merchant,
                        "amount": str(
                            transaction.amount
                        ),
                        "z_score": round(
                            z_score,
                            2,
                        ),
                        "reason": (
                            "Transaction exceeds "
                            "2.5 standard deviations "
                            "from the monthly expense mean."
                        ),
                    }
                )

        return anomalies

    async def get_budget_vs_actual(
        self,
        user_id,
        month: int,
        year: int,
    ):
        result = await self.db.execute(
            select(
                Budget,
                Category.name,
            )
            .join(
                Category,
                Budget.category_id == Category.id,
            )
            .where(
                Budget.user_id == user_id,
                Budget.month == month,
                Budget.year == year,
            )
        )

        rows = result.all()

        output = []

        for budget, category_name in rows:
            actual_result = await self.db.execute(
                select(
                    func.coalesce(
                        func.sum(Transaction.amount),
                        0,
                    )
                )
                .where(
                    Transaction.user_id == user_id,
                    Transaction.category_id
                    == budget.category_id,
                    Transaction.transaction_type
                    == TransactionType.EXPENSE,
                    func.extract(
                        "month",
                        Transaction.transaction_date,
                    )
                    == month,
                    func.extract(
                        "year",
                        Transaction.transaction_date,
                    )
                    == year,
                )
            )

            actual = Decimal(
                str(actual_result.scalar() or 0)
            )

            variance = budget.amount - actual

            utilization = (
                actual
                / budget.amount
                * Decimal("100")
                if budget.amount
                else Decimal("0")
            )

            if actual > budget.amount:
                status = "over_budget"
            elif utilization >= Decimal("80"):
                status = "near_limit"
            else:
                status = "within_budget"

            output.append(
                {
                    "category": category_name,
                    "budget": budget.amount,
                    "actual": actual,
                    "variance": variance,
                    "utilization_percent": utilization,
                    "status": status,
                }
            )

        return output

    async def get_committed_spend(
        self,
        user_id,
    ):
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        Subscription.average_amount
                    ),
                    0,
                )
            )
            .where(
                Subscription.user_id == user_id,
                Subscription.active.is_(True),
            )
        )

        return Decimal(
            str(result.scalar() or 0)
        )

    async def _category_totals(
        self,
        user_id,
        month,
        year,
    ):
        result = await self.db.execute(
            select(
                Category.name,
                func.sum(Transaction.amount),
            )
            .join(
                Category,
                Transaction.category_id == Category.id,
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_type
                == TransactionType.EXPENSE,
                func.extract(
                    "month",
                    Transaction.transaction_date,
                )
                == month,
                func.extract(
                    "year",
                    Transaction.transaction_date,
                )
                == year,
            )
            .group_by(Category.name)
        )

        return {
            category: Decimal(str(amount))
            for category, amount in result.all()
        }