"""Database operations for authorized users and result reports."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    AccountType,
    CheckBatch,
    CheckResult,
    CheckStatus,
    User,
)


@dataclass(frozen=True, slots=True)
class CheckResultInput:
    """Credential-free data required to record one check result."""

    account_type: AccountType
    account_label: str
    status: CheckStatus


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    """Return the user for a Telegram ID, adding it if it is not present."""
    if telegram_id <= 0:
        raise ValueError("telegram_id must be a positive integer.")

    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(telegram_id=telegram_id)
    try:
        async with session.begin_nested():
            session.add(user)
            await session.flush()
    except IntegrityError:
        # Another update for the same user inserted the row first.
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one()
    return user


async def record_check_batch(
    session: AsyncSession,
    user_id: int,
    results: list[CheckResultInput],
) -> CheckBatch:
    """Record results and derive report totals from those exact results."""
    if user_id <= 0:
        raise ValueError("user_id must be a positive integer.")
    if not results:
        raise ValueError("A check batch must contain at least one result.")

    for item in results:
        label = item.account_label.strip()
        if not label or len(label) > 100:
            raise ValueError("account_label must contain 1 to 100 characters.")

    success_count = sum(item.status is CheckStatus.SUCCESS for item in results)
    invalid_count = sum(
        item.status is CheckStatus.INVALID_CREDENTIALS for item in results
    )
    unknown_count = sum(item.status is CheckStatus.UNKNOWN for item in results)

    batch = CheckBatch(
        user_id=user_id,
        total_count=len(results),
        success_count=success_count,
        invalid_count=invalid_count,
        unknown_count=unknown_count,
        check_results=[
            CheckResult(
                account_type=item.account_type.value,
                account_label=item.account_label.strip(),
                status=item.status.value,
            )
            for item in results
        ],
    )
    session.add(batch)
    await session.flush()
    return batch


async def get_user_history(
    session: AsyncSession,
    telegram_id: int,
    limit: int = 10,
) -> list[CheckBatch]:
    """Return recent result summaries for one Telegram user."""
    if telegram_id <= 0:
        raise ValueError("telegram_id must be a positive integer.")
    if limit <= 0:
        raise ValueError("limit must be a positive integer.")

    statement = (
        select(CheckBatch)
        .join(User, CheckBatch.user_id == User.id)
        .where(User.telegram_id == telegram_id)
        .order_by(CheckBatch.created_at.desc(), CheckBatch.id.desc())
        .limit(limit)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())
