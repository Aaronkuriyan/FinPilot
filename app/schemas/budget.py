import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2000, le=2100)
    amount: Decimal = Field(gt=0)


class BudgetResponse(BudgetCreate):
    id: uuid.UUID
    user_id: uuid.UUID


class BudgetActual(BaseModel):
    category_id: uuid.UUID
    budget: Decimal
    actual: Decimal
    remaining: Decimal
    utilization_percent: Decimal
    status: str