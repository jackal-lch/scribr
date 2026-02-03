from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User

# Fixed UUID string for the default single user
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Get or create the default user for single-user mode.
    No authentication required.
    """
    result = await db.execute(
        select(User).where(User.id == DEFAULT_USER_ID)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Create default user on first request
        user = User(
            id=DEFAULT_USER_ID,
            email="user@local",
            name="Local User",
            google_id="local",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


# Type alias for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
