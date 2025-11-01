import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel


class User(BaseModel):
    user_id: str
    waifu_id: str
    updated_at: datetime = None
    user_name: Optional[str] = None
    relation: Optional[str] = None


class Waifu(BaseModel):
    waifu_id: str
    updated_at: datetime = None
    waifu_name: str
    is_active: bool = False
    speech_service: Optional[str] = None
    speaker: Optional[str] = None
    shared_context_id: str


class Context(BaseModel):
    context_id: str
    updated_at: datetime = None
    user_id: str
    waifu_id: str


class UserRepository:
    def __init__(self, connection_str: str):
        self.connection_str = connection_str
        self.create_table()

    def get_connection(self):
        conn = sqlite3.connect(self.connection_str)
        conn.row_factory = sqlite3.Row
        return conn

    def create_table(self):
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT NOT NULL,
                    waifu_id TEXT NOT NULL,
                    updated_at TEXT,
                    user_name TEXT,
                    relation TEXT,
                    PRIMARY KEY (user_id, waifu_id)
                )
                """
            )
            conn.commit()

    def get_user(self, user_id: str, waifu_id: str) -> Optional[User]:
        if not user_id:
            return None

        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, waifu_id, user_name, relation, updated_at FROM users WHERE user_id = ? AND waifu_id = ?",
                (user_id, waifu_id),
            ).fetchone()
        if row is None:
            return None

        updated_at = datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        return User(
            user_id=row["user_id"],
            waifu_id=row["waifu_id"],
            user_name=row["user_name"],
            relation=row["relation"],
            updated_at=updated_at
        )

    def user_exists(self, user_id: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                (user_id, ),
            ).fetchone()
        return row is not None

    def update_user(self, user_id: str, waifu_id: str, user_name: str = None, relation: str = None) -> User:
        now = datetime.now(timezone.utc)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, waifu_id, user_name, relation, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, waifu_id) DO UPDATE SET
                    user_name = excluded.user_name,
                    relation = excluded.relation,
                    updated_at = excluded.updated_at
                """,
                (user_id, waifu_id, user_name, relation, now.isoformat()),
            )
            conn.commit()
        return User(user_id=user_id, waifu_id=waifu_id, user_name=user_name, relation=relation, updated_at=now)

    def delete_user(self, user_id: str, waifu_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM users WHERE user_id = ? and waifu_id = ?", (user_id, waifu_id))
            conn.commit()


class WaifuRepository:
    def __init__(self, connection_str: str):
        self.connection_str = connection_str
        self.create_table()

    def get_connection(self):
        conn = sqlite3.connect(self.connection_str)
        conn.row_factory = sqlite3.Row
        return conn

    def create_table(self):
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS waifus (
                    waifu_id TEXT PRIMARY KEY,
                    waifu_name TEXT,
                    updated_at TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    speech_service TEXT,
                    speaker TEXT,
                    shared_context_id TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_waifus_active
                ON waifus (is_active)
                WHERE is_active = 1
                """
            )
            conn.commit()

    def get_waifu(self, waifu_id: str = None) -> Optional[Waifu]:
        with self.get_connection() as conn:
            if waifu_id:
                row = conn.execute(
                    """
                    SELECT waifu_id, waifu_name, updated_at, is_active, speech_service, speaker, shared_context_id
                    FROM waifus
                    WHERE waifu_id = ?
                    """,
                    (waifu_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT waifu_id, waifu_name, updated_at, is_active, speech_service, speaker, shared_context_id
                    FROM waifus
                    WHERE is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ).fetchone()
        if row is None:
            return None
        updated_at = datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
        return Waifu(
            waifu_id=row["waifu_id"],
            waifu_name=row["waifu_name"],
            updated_at=updated_at,
            is_active=bool(row["is_active"]),
            speech_service=row["speech_service"],
            speaker=row["speaker"],
            shared_context_id=row["shared_context_id"],
        )

    def get_waifus(self) -> List[Waifu]:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT waifu_id, waifu_name, updated_at, is_active, speech_service, speaker, shared_context_id FROM waifus"
            ).fetchall()
        return [
            Waifu(
                waifu_id=row["waifu_id"],
                waifu_name=row["waifu_name"],
                updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
                is_active=bool(row["is_active"]),
                speech_service=row["speech_service"],
                speaker=row["speaker"],
                shared_context_id=row["shared_context_id"],
            ) for row in rows]

    def update_waifu(
        self,
        waifu_id: str = None,
        waifu_name: str = None,
        is_active: bool = None,
        speech_service: Optional[str] = None,
        speaker: Optional[str] = None,
    ) -> Waifu:
        now = datetime.now(timezone.utc)
        with self.get_connection() as conn:
            # Get target waifu
            if waifu_id:
                row = conn.execute(
                    """
                    SELECT waifu_id, waifu_name, updated_at, is_active, speech_service, speaker, shared_context_id
                    FROM waifus
                    WHERE waifu_id = ?
                    """,
                    (waifu_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT waifu_id, waifu_name, updated_at, is_active, speech_service, speaker, shared_context_id
                    FROM waifus
                    WHERE is_active = 1
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """
                ).fetchone()
                if not row:
                    return None

            target_waifu_id = waifu_id or row["waifu_id"]
            updated_waifu_name = waifu_name or row["waifu_name"]
            updated_is_active = is_active if is_active is not None else bool(row["is_active"])
            updated_speech_service = (
                speech_service if speech_service is not None else (row["speech_service"] if row else None)
            )
            updated_speaker = speaker if speaker is not None else (row["speaker"] if row else None)
            shared_context_id = (
                row["shared_context_id"] if row and row["shared_context_id"] else f"ctx_{target_waifu_id}"
            )

            if is_active:
                conn.execute(
                    "UPDATE waifus SET is_active = 0 WHERE is_active = 1 AND waifu_id != ?",
                    (target_waifu_id,),
                )
            conn.execute(
                """
                INSERT INTO waifus (waifu_id, waifu_name, updated_at, is_active, speech_service, speaker, shared_context_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(waifu_id) DO UPDATE SET
                    waifu_name = excluded.waifu_name,
                    updated_at = excluded.updated_at,
                    is_active = excluded.is_active,
                    speech_service = excluded.speech_service,
                    speaker = excluded.speaker
                """,
                (
                    target_waifu_id,
                    updated_waifu_name,
                    now.isoformat(),
                    int(updated_is_active),
                    updated_speech_service,
                    updated_speaker,
                    shared_context_id,
                ),
            )
            conn.commit()

        return Waifu(
            waifu_id=target_waifu_id,
            waifu_name=updated_waifu_name,
            updated_at=now,
            is_active=updated_is_active,
            speech_service=updated_speech_service,
            speaker=updated_speaker,
            shared_context_id=shared_context_id,
        )

    def delete_waifu(self, waifu_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM waifus WHERE waifu_id = ?", (waifu_id,))
            conn.commit()


class ContextRepository:
    def __init__(self, connection_str: str):
        self.connection_str = connection_str
        self.create_table()

    def get_connection(self):
        conn = sqlite3.connect(self.connection_str)
        conn.row_factory = sqlite3.Row
        return conn

    def create_table(self):
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contexts (
                    user_id TEXT NOT NULL,
                    waifu_id TEXT NOT NULL,
                    context_id TEXT NOT NULL,
                    updated_at TEXT,
                    PRIMARY KEY (user_id, waifu_id),
                    UNIQUE(context_id)
                )
                """
            )
            conn.commit()

    def get_context(self, user_id: str, waifu_id: str) -> Context:
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT context_id, updated_at
                FROM contexts
                WHERE user_id = ? AND waifu_id = ?
                """,
                (user_id, waifu_id),
            ).fetchone()

            if row:
                return Context(
                    context_id=row["context_id"],
                    user_id=user_id,
                    waifu_id=waifu_id,
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            
            return None

    def get_context_ids(self, waifu_id: str) -> List[str]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT context_id
                FROM contexts
                WHERE waifu_id = ?
                """,
                (waifu_id, ),
            ).fetchall()

            return [row["context_id"] for row in rows]

    def update_context(self, context_id: str, user_id: str, waifu_id: str) -> Context:
        now = datetime.now(timezone.utc)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO contexts (user_id, waifu_id, context_id, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, waifu_id) DO UPDATE SET
                    context_id = excluded.context_id,
                    updated_at = excluded.updated_at
                """,
                (user_id, waifu_id, context_id, now.isoformat()),
            )
            conn.commit()

        return Context(context_id=context_id, user_id=user_id, waifu_id=waifu_id, updated_at=now)

    def remove_context(self, user_id: str = None, waifu_id: str = None):
        query = "DELETE FROM contexts"
        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if waifu_id:
            conditions.append("waifu_id = ?")
            params.append(waifu_id)

        if conditions:
            query = f"{query} WHERE {' AND '.join(conditions)}"

        with self.get_connection() as conn:
            conn.execute(query, params)
            conn.commit()
