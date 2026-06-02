from app.core.database import DatabaseManager
from app.features.email.models import (  # noqa: F401
    EmailMessage,
    EmailSender,
)
from app.features.nat.models import (  # noqa: F401
    NatBatch,
    NatDedupKey,
    NatIntake,
    NatIntakeRowError,
    NatTask,
)
from email_poller.app.core.config import settings

db_manager = DatabaseManager()


def init_db() -> None:
    db_manager.init(
        database_url=settings.DB_URL,
        db_echo=settings.DB_ECHO,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )
