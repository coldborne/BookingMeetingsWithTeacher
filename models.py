from sqlalchemy import Column, Integer, String, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, nullable=False)
    name = Column(String(255), nullable=True)
    surname = Column(String(255), nullable=True)
    language = Column(String(50), nullable=True)
    state = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class UserDTO:
    def __init__(self, telegram_id: int, name: str = None, surname: str = None,
                 language: str = None, state: str = None):
        self.telegram_id = telegram_id
        self.name = name
        self.surname = surname
        self.language = language
        self.state = state