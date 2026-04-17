"""Email account management — list / create / update / delete / test connection."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_session
from app.db.services.email_accounts import (
    account_to_dict,
    create_account,
    delete_account,
    get_account,
    list_accounts,
    test_connection,
    update_account,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email-accounts")


class EmailAccountCreate(BaseModel):
    label: str
    email_address: str = ""
    imap_host: str
    imap_port: int = 993
    imap_user: str
    imap_password: str
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    is_default: bool = False
    sync_enabled: bool = True


class EmailAccountUpdate(BaseModel):
    label: str | None = None
    email_address: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    imap_password: str | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    is_default: bool | None = None
    sync_enabled: bool | None = None


@router.get("")
async def list_email_accounts(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await list_accounts(session)
    return {"accounts": [account_to_dict(r) for r in rows], "total": len(rows)}


@router.post("")
async def create_email_account(
    body: EmailAccountCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not body.label.strip():
        raise HTTPException(status_code=400, detail="label is required.")
    try:
        acct = await create_account(session, **body.model_dump())
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create account: {exc}") from exc
    return account_to_dict(acct)


@router.patch("/{account_id}")
async def patch_email_account(
    account_id: int,
    body: EmailAccountUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    payload = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    acct = await update_account(session, account_id, **payload)
    if not acct:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    await session.commit()
    return account_to_dict(acct)


@router.delete("/{account_id}")
async def delete_email_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    deleted = await delete_account(session, account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    await session.commit()
    return {"id": account_id, "deleted": True}


@router.post("/{account_id}/test")
async def test_email_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    acct = await get_account(session, account_id)
    if not acct:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found.")
    result = await test_connection(acct)
    return {"account_id": account_id, **result}
