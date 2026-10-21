"""Session factories used by services, including scanner lock-bound sessions."""
from contextlib import AbstractAsyncContextManager
from typing import Protocol
from sqlalchemy.ext.asyncio import AsyncSession


class SessionProvider(Protocol):
    def __call__(self) -> AsyncSession: ...

    def begin(self) -> AbstractAsyncContextManager[AsyncSession]: ...
