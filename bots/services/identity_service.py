from sqlalchemy import text

from bots.config.logging_config import get_logger
from bots.config.platforms import Platforms
from bots.models.database import Database
from bots.models.models import UserDTO
from bots.services.user_service import UserService
from bots.utils.cryptographer import encrypt_platform_user_id

logger = get_logger(__name__)


class IdentityService:
    def __init__(self, database: Database, user_service: UserService):
        self.__database = database
        self.__user_service = user_service

    def __normalize_platform_user_id(self, platform_user_id: int | str) -> str:
        normalized_value = str(platform_user_id).strip()

        if not normalized_value:
            raise ValueError("platform_user_id не может быть пустым")

        return normalized_value

    def __encrypt_identity(self, platform_user_id: int | str) -> str:
        normalized_value = self.__normalize_platform_user_id(platform_user_id)
        return encrypt_platform_user_id(normalized_value)

    async def get_identity(self, platform: str, platform_user_id: int | str) -> dict | None:
        encrypted_platform_user_id = self.__encrypt_identity(platform_user_id)

        async def query():
            session = await self.__database.get_session()

            try:
                query_text = text(
                    """
                    SELECT id, user_id, platform, platform_user_id, created_at
                    FROM user_identities
                    WHERE platform = :platform
                      AND platform_user_id = :platform_user_id
                    LIMIT 1
                    """
                )
                result = session.execute(
                    query_text,
                    {
                        "platform": platform,
                        "platform_user_id": encrypted_platform_user_id,
                    },
                ).mappings().first()

                return dict(result) if result else None
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def create_identity(self, user_id: int, platform: str, platform_user_id: int | str) -> dict | None:
        encrypted_platform_user_id = self.__encrypt_identity(platform_user_id)

        async def query():
            session = await self.__database.get_session()

            try:
                insert_query_text = text(
                    """
                    INSERT INTO user_identities (user_id, platform, platform_user_id)
                    VALUES (:user_id, :platform, :platform_user_id)
                    """
                )
                session.execute(
                    insert_query_text,
                    {
                        "user_id": user_id,
                        "platform": platform,
                        "platform_user_id": encrypted_platform_user_id,
                    },
                )
                session.commit()

                select_query_text = text(
                    """
                    SELECT id, user_id, platform, platform_user_id, created_at
                    FROM user_identities
                    WHERE platform = :platform
                      AND platform_user_id = :platform_user_id
                    LIMIT 1
                    """
                )
                result = session.execute(
                    select_query_text,
                    {
                        "platform": platform,
                        "platform_user_id": encrypted_platform_user_id,
                    },
                ).mappings().first()

                return dict(result) if result else None
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def get_user_by_identity(self, platform: str, platform_user_id: int | str) -> UserDTO | None:
        identity = await self.get_identity(platform, platform_user_id)

        if identity:
            return await self.__user_service.get_user_by_id(identity["user_id"])

        normalized_platform_user_id = self.__normalize_platform_user_id(platform_user_id)

        if platform == Platforms.TELEGRAM:
            legacy_user = await self.__user_service.get_user_by_telegram_id(int(normalized_platform_user_id))
            if legacy_user:
                await self.create_identity(legacy_user.id, platform, normalized_platform_user_id)
                return legacy_user

        return None

    async def get_or_create_user_by_identity(self, platform: str, platform_user_id: int | str) -> UserDTO | None:
        user = await self.get_user_by_identity(platform, platform_user_id)

        if user:
            return user

        normalized_platform_user_id = self.__normalize_platform_user_id(platform_user_id)

        if platform == Platforms.TELEGRAM:
            created_user = await self.__user_service.create_user(telegram_id=int(normalized_platform_user_id))
        else:
            created_user = await self.__user_service.create_user()

        if not created_user:
            logger.error(
                f"Не удалось создать пользователя для platform={platform}, platform_user_id={normalized_platform_user_id}"
            )
            return None

        await self.create_identity(created_user.id, platform, normalized_platform_user_id)
        return created_user

    async def bind_identity_to_user(self, user_id: int, platform: str, platform_user_id: int | str) -> None:
        encrypted_platform_user_id = self.__encrypt_identity(platform_user_id)

        async def query():
            session = await self.__database.get_session()

            try:
                query_text = text(
                    """
                    UPDATE user_identities
                    SET user_id = :user_id
                    WHERE platform = :platform
                      AND platform_user_id = :platform_user_id
                    """
                )
                session.execute(
                    query_text,
                    {
                        "user_id": user_id,
                        "platform": platform,
                        "platform_user_id": encrypted_platform_user_id,
                    },
                )
                session.commit()
            finally:
                await self.__database.close_session()

        await self.__database.execute_with_retry(query)