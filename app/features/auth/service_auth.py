from app.features.auth.constants import (
    EMAIL_POLLER_SERVICE_ROLE,
    SENDER_MANAGER_ROLE,
)
from app.features.auth.schemas import User


def is_email_poller_service_user(user: User, *, expected_client_id: str) -> bool:
    if user.authorized_party != expected_client_id:
        return False
    return EMAIL_POLLER_SERVICE_ROLE in user.roles


def can_manage_email_senders(user: User, *, admin_roles: set[str]) -> bool:
    if SENDER_MANAGER_ROLE in user.roles:
        return True
    return any(role in admin_roles for role in user.roles)
