from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class SpendingItem(BaseModel):
    category: str
    amount: Decimal
    percentage: Decimal


class MonthlyAnalytics(BaseModel):
    month: int
    year: int
    income: Decimal
    expenses: Decimal
    net_cash_flow: Decimal
    burn_rate: Decimal
    top_spending: list[SpendingItem]
    anomalies: list[dict[str, Any]]


class BudgetVsActual(BaseModel):
    category: str
    budget: Decimal
    actual: Decimal
    variance: Decimal
    utilization_percent: Decimal


class ExpenseIncrease(BaseModel):
    category: str
    current_amount: Decimal
    comparison_amount: Decimal
    absolute_change: Decimal
    percentage_change: Decimal