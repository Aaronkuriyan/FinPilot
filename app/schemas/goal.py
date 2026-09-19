import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal = Field(gt=0)
    current_amount: Decimal = Field(default=0, ge=0)
    target_date: date


class GoalUpdate(BaseModel):
    current_amount: Decimal | None = Field(default=None, ge=0)
    monthly_contribution: Decimal | None = Field(default=None, ge=0)


class GoalResponse(GoalCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    monthly_contribution: Decimal


class GoalImpactResponse(BaseModel):
    goal_id: uuid.UUID
    planned_expense: Decimal
    remaining_goal_amount: Decimal
    months_to_target: int
    required_monthly_contribution: Decimal
    contribution_gap: Decimal
    projected_target_date: date | None