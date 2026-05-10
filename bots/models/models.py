from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String
from sqlalchemy.sql import func

from bots.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, nullable=True)
    name = Column(String(255), nullable=True)
    surname = Column(String(255), nullable=True)
    language = Column(String(50), nullable=True)
    state = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    is_banned = Column(Boolean, nullable=False, default=False)
    hour_rate = Column(Integer, nullable=False, default=1500)


class UserDTO:
    def __init__(
        self,
        id: int,
        telegram_id: int | None = None,
        name: str | None = None,
        surname: str | None = None,
        language: str | None = None,
        state: str | None = None,
        hour_rate: int | None = None,
        is_banned: bool = False,
    ):
        self.id = id
        self.telegram_id = telegram_id
        self.name = name
        self.surname = surname
        self.language = language
        self.state = state
        self.hour_rate = hour_rate
        self.is_banned = is_banned