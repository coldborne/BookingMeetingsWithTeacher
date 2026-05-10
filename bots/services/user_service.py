from sqlalchemy.exc import IntegrityError

from bots.config.logging_config import get_logger
from bots.models.database import Database
from bots.models.models import User, UserDTO
from bots.utils.cryptographer import encrypt_telegram_id

logger = get_logger(__name__)


class UserService:
    def __init__(self, database: Database):
        self.__database = database

    def __to_dto(self, user: User, original_telegram_id: int | None = None) -> UserDTO | None:
        if user:
            return UserDTO(
                id=user.id,
                telegram_id=original_telegram_id,
                name=user.name,
                surname=user.surname,
                language=user.language,
                state=user.state,
                hour_rate=user.hour_rate,
                is_banned=user.is_banned,
            )
        return None

    async def get_user_by_id(self, user_id: int) -> UserDTO | None:
        async def query():
            session = await self.__database.get_session()

            try:
                user = session.query(User).filter(User.id == user_id).first()
                return self.__to_dto(user)
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def get_user_by_telegram_id(self, telegram_id: int) -> UserDTO | None:
        async def query():
            session = await self.__database.get_session()

            try:
                encrypted_id = encrypt_telegram_id(telegram_id)
                user = session.query(User).filter(User.telegram_id == encrypted_id).first()
                return self.__to_dto(user, telegram_id)
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def create_user(self, telegram_id: int | None = None) -> UserDTO | None:
        async def query():
            session = await self.__database.get_session()
            encrypted_id = None

            try:
                if telegram_id is not None:
                    encrypted_id = encrypt_telegram_id(telegram_id)

                user = User(telegram_id=encrypted_id)
                session.add(user)
                session.commit()
                session.refresh(user)

                return self.__to_dto(user, telegram_id)
            except IntegrityError:
                session.rollback()
                logger.warning(f"Пользователь с telegram_id={encrypted_id} уже существует")
                return None
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def update_user_by_id(self, user_id: int, **kwargs) -> UserDTO | None:
        async def query():
            session = await self.__database.get_session()

            try:
                user = session.query(User).filter(User.id == user_id).first()

                if user:
                    for key, value in kwargs.items():
                        setattr(user, key, value)

                    session.commit()
                    session.refresh(user)
                    return self.__to_dto(user)

                logger.warning(f"Пользователь с id={user_id} не найден для обновления")
                return None
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def update_user(self, telegram_id: int, **kwargs) -> UserDTO | None:
        async def query():
            session = await self.__database.get_session()

            try:
                encrypted_id = encrypt_telegram_id(telegram_id)
                user = session.query(User).filter(User.telegram_id == encrypted_id).first()

                if user:
                    for key, value in kwargs.items():
                        setattr(user, key, value)

                    session.commit()
                    session.refresh(user)
                    return self.__to_dto(user, telegram_id)

                logger.warning(f"Пользователь с telegram_id={encrypted_id} не найден для обновления")
                return None
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def get_user_state(self, telegram_id: int) -> str | None:
        async def query():
            session = await self.__database.get_session()

            try:
                encrypted_id = encrypt_telegram_id(telegram_id)
                user = session.query(User).filter(User.telegram_id == encrypted_id).first()
                return user.state if user else None
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def set_user_state(self, telegram_id: int, state: str):
        await self.update_user(telegram_id, state=state)