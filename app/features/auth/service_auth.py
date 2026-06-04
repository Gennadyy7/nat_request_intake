from app.features.auth.constants import EMAIL_POLLER_SERVICE_ROLE
from app.features.auth.schemas import User


def is_email_poller_service_user(user: User, *, expected_client_id: str) -> bool:
    if user.authorized_party != expected_client_id:
        return False
    return EMAIL_POLLER_SERVICE_ROLE in user.roles
