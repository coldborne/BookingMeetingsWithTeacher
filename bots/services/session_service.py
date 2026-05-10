import json

from sqlalchemy import text

from bots.models.database import Database


class SessionService:
    def __init__(self, database: Database):
        self.__database = database

    async def get_session(self, user_id: int, platform: str) -> dict | None:
        async def query():
            session = await self.__database.get_session()

            try:
                query_text = text(
                    """
                    SELECT id, user_id, platform, state, state_payload, updated_at
                    FROM user_sessions
                    WHERE user_id = :user_id
                      AND platform = :platform
                    LIMIT 1
                    """
                )
                result = session.execute(
                    query_text,
                    {
                        "user_id": user_id,
                        "platform": platform,
                    },
                ).mappings().first()

                if not result:
                    return None

                row = dict(result)

                if row["state_payload"] is None:
                    row["state_payload"] = {}
                elif isinstance(row["state_payload"], str):
                    row["state_payload"] = json.loads(row["state_payload"])

                return row
            finally:
                await self.__database.close_session()

        return await self.__database.execute_with_retry(query)

    async def get_state(self, user_id: int, platform: str) -> str | None:
        session = await self.get_session(user_id, platform)
        return session["state"] if session else None

    async def get_payload(self, user_id: int, platform: str) -> dict:
        session = await self.get_session(user_id, platform)
        return session["state_payload"] if session else {}

    async def set_state(self, user_id: int, platform: str, state: str | None, payload: dict | None = None) -> None:
        if payload is None:
            payload = {}

        async def query():
            session = await self.__database.get_session()

            try:
                query_text = text(
                    """
                    INSERT INTO user_sessions (user_id, platform, state, state_payload)
                    VALUES (:user_id, :platform, :state, :state_payload)
                    ON DUPLICATE KEY UPDATE
                        state = VALUES(state),
                        state_payload = VALUES(state_payload),
                        updated_at = CURRENT_TIMESTAMP
                    """
                )
                session.execute(
                    query_text,
                    {
                        "user_id": user_id,
                        "platform": platform,
                        "state": state,
                        "state_payload": json.dumps(payload, ensure_ascii=False),
                    },
                )
                session.commit()
            finally:
                await self.__database.close_session()

        await self.__database.execute_with_retry(query)

    async def update_payload(self, user_id: int, platform: str, patch_data: dict) -> None:
        current_payload = await self.get_payload(user_id, platform)
        current_state = await self.get_state(user_id, platform)

        current_payload.update(patch_data)

        await self.set_state(
            user_id=user_id,
            platform=platform,
            state=current_state,
            payload=current_payload,
        )

    async def clear_state(self, user_id: int, platform: str) -> None:
        await self.set_state(user_id, platform, None, {})
