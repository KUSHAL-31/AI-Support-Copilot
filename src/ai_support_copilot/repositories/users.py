from uuid import UUID

from ai_support_copilot.domain.models import User


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRepository:
    def __init__(self) -> None:
        self._users: dict[UUID, User] = {}
        self._ids_by_email: dict[str, UUID] = {}

    async def create(self, user: User) -> User:
        email = _normalize_email(user.email)
        if email in self._ids_by_email:
            raise ValueError("email already registered")
        user.email = email
        self._users[user.id] = user
        self._ids_by_email[email] = user.id
        return user

    async def get_by_email(self, email: str) -> User | None:
        user_id = self._ids_by_email.get(_normalize_email(email))
        return self._users.get(user_id) if user_id else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)


user_repository = UserRepository()
