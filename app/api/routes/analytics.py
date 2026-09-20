from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.analytics import (
    BudgetVsActual,
    ExpenseIncrease,
    MonthlyAnalytics,
    SpendingItem,
)
from app.services.analytics_service import AnalyticsService


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get("/monthly", response_model=MonthlyAnalytics)
async def monthly_analytics(
    user_id: UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)

    summary = await service.get_month_summary(
        user_id=user_id,
        month=month,
        year=year,
    )

    top_spending = await service.get_top_spending(
        user_id=user_id,
        month=month,
        year=year,
    )

    anomalies = await service.detect_anomalies(
        user_id=user_id,
        month=month,
        year=year,
    )

    return {
        **summary,
        "top_spending": top_spending,
        "anomalies": anomalies,
    }


@router.get("/top-spending", response_model=list[SpendingItem])
async def top_spending(
    user_id: UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)

    return await service.get_top_spending(
        user_id=user_id,
        month=month,
        year=year,
        limit=limit,
    )


@router.get("/expense-increases", response_model=list[ExpenseIncrease])
async def expense_increases(
    user_id: UUID,
    current_month: int = Query(..., ge=1, le=12),
    current_year: int = Query(..., ge=2000, le=2100),
    comparison_month: int = Query(..., ge=1, le=12),
    comparison_year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)

    return await service.get_expense_increases(
        user_id=user_id,
        current_month=current_month,
        current_year=current_year,
        comparison_month=comparison_month,
        comparison_year=comparison_year,
    )


@router.get("/budget-vs-actual", response_model=list[BudgetVsActual])
async def budget_vs_actual(
    user_id: UUID,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)

    return await service.get_budget_vs_actual(
        user_id=user_id,
        month=month,
        year=year,
    )


@router.get("/committed-spend")
async def committed_spend(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)

    amount = await service.get_committed_spend(
        user_id=user_id,
    )

    return {
        "committed_spend": amount,
        "currency": "INR",
    }