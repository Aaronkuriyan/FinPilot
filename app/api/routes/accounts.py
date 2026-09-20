from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountResponse


router = APIRouter(
    prefix="/accounts",
    tags=["Accounts"],
)


@router.get("", response_model=list[AccountResponse])
async def get_accounts(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Account)
        .where(Account.user_id == user_id)
        .order_by(Account.created_at.desc())
    )

    return list(result.scalars().all())


@router.post("", response_model=AccountResponse)
async def create_account(
    account_data: AccountCreate,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    account = Account(
        user_id=user_id,
        name=account_data.name,
        account_type=account_data.account_type,
        institution=account_data.institution,
        last_four=account_data.last_four,
        currency=account_data.currency,
    )

    db.add(account)
    await db.commit()
    await db.refresh(account)

    return account