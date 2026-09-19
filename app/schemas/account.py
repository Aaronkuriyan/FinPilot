import uuid

from pydantic import BaseModel, ConfigDict

from app.models.account import AccountType


class AccountCreate(BaseModel):
    name: str
    account_type: AccountType
    institution: str | None = None
    last_four: str | None = None
    currency: str = "INR"


class AccountResponse(AccountCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID