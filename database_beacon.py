"""
Vouch Beacon Database Module
Implements the full Vouch Beacon ecosystem schema
"""
import asyncpg
import os
import json
import jwt
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# JWT secret for magic links
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-this")

class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv("DATABASE_URL")

    async def connect(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database pool created successfully")
            await self.init_schema()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    def _ensure_connected(self) -> asyncpg.Pool:
        """Ensure database pool is connected and return it (type guard)"""
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        return self.pool

    async def init_schema(self):
        """Create all necessary tables - VOUCH BEACON SCHEMA"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Users table - Vouch Beacon design
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_user_id BIGINT UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    is_known_user BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_seen_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create index on telegram_user_id for fast lookups
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                ON users(telegram_user_id)
            """)

            # Vouches table - Vouch Beacon design with group support
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS vouches (
                    id SERIAL PRIMARY KEY,
                    from_user_id INTEGER REFERENCES users(id),
                    to_user_id INTEGER REFERENCES users(id) NOT NULL,
                    group_chat_id BIGINT,
                    comment TEXT,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Indexes for vouches
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vouches_from_user
                ON vouches(from_user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vouches_to_user
                ON vouches(to_user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vouches_group
                ON vouches(group_chat_id)
            """)

            # Group Config table - For multi-group support
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS group_config (
                    id SERIAL PRIMARY KEY,
                    group_chat_id BIGINT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    config_options JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Events/Analytics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    user_id INTEGER,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type
                ON events(event_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_created
                ON events(created_at)
            """)

            logger.info("Vouch Beacon database schema initialized successfully")

    # ==================== USER OPERATIONS ====================

    async def get_or_create_user(self, telegram_user_id: int, username: Optional[str] = None,
                                  first_name: Optional[str] = None) -> Dict[str, Any]:
        """Get user or create if doesn't exist"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )

            if user:
                # Update last seen and username if provided
                if username:
                    await conn.execute(
                        """UPDATE users SET
                           last_seen_at = NOW(),
                           username = $2
                           WHERE telegram_user_id = $1""",
                        telegram_user_id, username
                    )
                else:
                    await conn.execute(
                        "UPDATE users SET last_seen_at = NOW() WHERE telegram_user_id = $1",
                        telegram_user_id
                    )
                # Refetch to get updated data
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE telegram_user_id = $1",
                    telegram_user_id
                )
                return dict(user)
            else:
                # Create new user
                user = await conn.fetchrow("""
                    INSERT INTO users (telegram_user_id, username, first_name, is_known_user)
                    VALUES ($1, $2, $3, FALSE)
                    RETURNING *
                """, telegram_user_id, username, first_name)

                await self.log_event("user_signup", user["id"], {
                    "username": username,
                    "first_name": first_name
                })

                return dict(user)

    async def mark_user_as_known(self, telegram_user_id: int):
        """Mark user as known (completed Welcome Mat)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_known_user = TRUE WHERE telegram_user_id = $1",
                telegram_user_id
            )

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram ID"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            return dict(user) if user else None

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by internal ID"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            return dict(user) if user else None

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username (case-insensitive)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE LOWER(username) = LOWER($1)",
                username.replace("@", "")
            )
            return dict(user) if user else None

    # ==================== VOUCH OPERATIONS ====================

    async def create_vouch(self, from_telegram_id: int, to_username: str,
                          group_chat_id: Optional[int] = None,
                          comment: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new vouch
        Returns: vouch record with vouch_id
        """
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Get from_user
            from_user = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_user_id = $1",
                from_telegram_id
            )
            if not from_user:
                return {"error": "Giver user not found"}

            # Find to_user by username
            to_user = await conn.fetchrow(
                "SELECT id, telegram_user_id FROM users WHERE LOWER(username) = LOWER($1)",
                to_username.replace("@", "")
            )
            if not to_user:
                return {"error": "User not found. They need to connect with the bot first!"}

            # Check for self-vouch
            if from_user["id"] == to_user["id"]:
                return {"error": "You cannot vouch for yourself"}

            # Check if vouch already exists (and not deleted)
            existing = await conn.fetchrow(
                """SELECT id FROM vouches
                   WHERE from_user_id = $1 AND to_user_id = $2 AND is_deleted = FALSE""",
                from_user["id"], to_user["id"]
            )
            if existing:
                return {"error": "You already vouched for this user"}

            # Create vouch
            vouch = await conn.fetchrow("""
                INSERT INTO vouches (from_user_id, to_user_id, group_chat_id, comment, is_deleted)
                VALUES ($1, $2, $3, $4, FALSE)
                RETURNING id, created_at
            """, from_user["id"], to_user["id"], group_chat_id, comment)

            await self.log_event("vouch_created", from_user["id"], {
                "to_user_id": to_user["id"],
                "group_chat_id": group_chat_id
            })

            return {
                "vouch_id": vouch["id"],
                "to_user_telegram_id": to_user["telegram_user_id"],
                "created_at": vouch["created_at"]
            }

    async def update_vouch_comment(self, vouch_id: int, from_telegram_id: int,
                                   comment: str) -> Dict[str, Any]:
        """Update vouch comment - only creator can update"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Verify ownership
            vouch = await conn.fetchrow("""
                SELECT v.*, u.telegram_user_id
                FROM vouches v
                JOIN users u ON v.from_user_id = u.id
                WHERE v.id = $1
            """, vouch_id)

            if not vouch:
                return {"error": "Vouch not found"}

            if vouch["telegram_user_id"] != from_telegram_id:
                return {"error": "You can only edit your own vouches"}

            # Update comment
            await conn.execute(
                "UPDATE vouches SET comment = $1 WHERE id = $2",
                comment, vouch_id
            )

            return {"success": True}

    async def undo_vouch(self, vouch_id: int, from_telegram_id: int) -> Dict[str, Any]:
        """Soft delete a vouch - only creator can undo"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Verify ownership
            vouch = await conn.fetchrow("""
                SELECT v.*, u.telegram_user_id
                FROM vouches v
                JOIN users u ON v.from_user_id = u.id
                WHERE v.id = $1
            """, vouch_id)

            if not vouch:
                return {"error": "Vouch not found"}

            if vouch["telegram_user_id"] != from_telegram_id:
                return {"error": "You can only undo your own vouches"}

            # Soft delete
            await conn.execute(
                "UPDATE vouches SET is_deleted = TRUE WHERE id = $1",
                vouch_id
            )

            await self.log_event("vouch_undone", vouch["from_user_id"], {
                "vouch_id": vouch_id
            })

            return {"success": True}

    async def get_vouches_for_user(self, telegram_user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get vouches received by a user (not deleted)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            vouches = await conn.fetch("""
                SELECT
                    v.id, v.comment, v.created_at, v.group_chat_id,
                    from_user.username as from_username,
                    from_user.first_name as from_first_name
                FROM vouches v
                JOIN users to_user ON v.to_user_id = to_user.id
                JOIN users from_user ON v.from_user_id = from_user.id
                WHERE to_user.telegram_user_id = $1 AND v.is_deleted = FALSE
                ORDER BY v.created_at DESC
                LIMIT $2
            """, telegram_user_id, limit)
            return [dict(v) for v in vouches]

    async def get_vouches_by_user(self, telegram_user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get vouches given by a user (not deleted)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            vouches = await conn.fetch("""
                SELECT
                    v.id, v.comment, v.created_at, v.group_chat_id,
                    to_user.username as to_username,
                    to_user.first_name as to_first_name
                FROM vouches v
                JOIN users from_user ON v.from_user_id = from_user.id
                JOIN users to_user ON v.to_user_id = to_user.id
                WHERE from_user.telegram_user_id = $1 AND v.is_deleted = FALSE
                ORDER BY v.created_at DESC
                LIMIT $2
            """, telegram_user_id, limit)
            return [dict(v) for v in vouches]

    async def get_user_stats(self, telegram_user_id: int) -> Dict[str, Any]:
        """Get comprehensive user stats"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Get user
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            if not user:
                return {"error": "User not found"}

            # Count vouches received
            vouches_received_count = await conn.fetchval("""
                SELECT COUNT(*) FROM vouches v
                JOIN users u ON v.to_user_id = u.id
                WHERE u.telegram_user_id = $1 AND v.is_deleted = FALSE
            """, telegram_user_id)

            # Count vouches given
            vouches_given_count = await conn.fetchval("""
                SELECT COUNT(*) FROM vouches v
                JOIN users u ON v.from_user_id = u.id
                WHERE u.telegram_user_id = $1 AND v.is_deleted = FALSE
            """, telegram_user_id)

            return {
                "user": dict(user),
                "vouches_received": vouches_received_count,
                "vouches_given": vouches_given_count
            }

    # ==================== LEADERBOARD OPERATIONS ====================

    async def get_leaderboard(self, board_type: str = "most_vouched", limit: int = 25) -> List[Dict[str, Any]]:
        """
        Get leaderboard data
        Types: most_vouched, top_givers
        """
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            if board_type == "most_vouched":
                users = await conn.fetch("""
                    SELECT
                        u.id, u.telegram_user_id, u.username, u.first_name,
                        COUNT(v.id) as vouch_count
                    FROM users u
                    LEFT JOIN vouches v ON u.id = v.to_user_id AND v.is_deleted = FALSE
                    GROUP BY u.id
                    HAVING COUNT(v.id) > 0
                    ORDER BY vouch_count DESC
                    LIMIT $1
                """, limit)
            elif board_type == "top_givers":
                users = await conn.fetch("""
                    SELECT
                        u.id, u.telegram_user_id, u.username, u.first_name,
                        COUNT(v.id) as vouch_count
                    FROM users u
                    LEFT JOIN vouches v ON u.id = v.from_user_id AND v.is_deleted = FALSE
                    GROUP BY u.id
                    HAVING COUNT(v.id) > 0
                    ORDER BY vouch_count DESC
                    LIMIT $1
                """, limit)
            else:
                return []

            return [dict(u) for u in users]

    # ==================== GROUP CONFIG OPERATIONS ====================

    async def get_or_create_group_config(self, group_chat_id: int) -> Dict[str, Any]:
        """Get or create group configuration"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            config = await conn.fetchrow(
                "SELECT * FROM group_config WHERE group_chat_id = $1",
                group_chat_id
            )

            if config:
                return dict(config)
            else:
                # Create default config
                config = await conn.fetchrow("""
                    INSERT INTO group_config (group_chat_id, is_active, config_options)
                    VALUES ($1, TRUE, '{}'::jsonb)
                    RETURNING *
                """, group_chat_id)
                return dict(config)

    async def update_group_config(self, group_chat_id: int, config_options: dict) -> Dict[str, Any]:
        """Update group configuration"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE group_config SET config_options = $1 WHERE group_chat_id = $2",
                json.dumps(config_options), group_chat_id
            )
            return {"success": True}

    # ==================== MAGIC LINK AUTHENTICATION ====================

    def generate_magic_link(self, telegram_user_id: int) -> str:
        """Generate a short-lived magic link JWT token"""
        payload = {
            "user_id": telegram_user_id,
            "exp": datetime.utcnow() + timedelta(minutes=15)  # 15 minute expiry
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        webapp_url = os.getenv("WEBHOOK_URL", "http://localhost:5000")
        return f"{webapp_url}/auth?token={token}"

    def verify_magic_link(self, token: str) -> Optional[int]:
        """Verify magic link token and return telegram_user_id"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            return payload.get("user_id")
        except jwt.ExpiredSignatureError:
            logger.warning("Magic link token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid magic link token")
            return None

    # ==================== ANALYTICS OPERATIONS ====================

    async def log_event(self, event_type: str, user_id: Optional[int] = None, metadata: Optional[Dict] = None):
        """Log an analytics event"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            metadata_json = json.dumps(metadata) if metadata else None
            await conn.execute("""
                INSERT INTO events (event_type, user_id, metadata)
                VALUES ($1, $2, $3)
            """, event_type, user_id, metadata_json)

    async def get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_vouches = await conn.fetchval("SELECT COUNT(*) FROM vouches WHERE is_deleted = FALSE")

            active_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE last_seen_at > NOW() - INTERVAL '24 hours'"
            )
            active_7d = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE last_seen_at > NOW() - INTERVAL '7 days'"
            )

            return {
                "total_users": total_users,
                "total_vouches": total_vouches,
                "active_users": {
                    "24h": active_24h,
                    "7d": active_7d
                }
            }

# Global database instance
db = Database()
