"""
Database module for Vouch Portal
Handles PostgreSQL connections and schema management
"""
import asyncpg
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        """Create all necessary tables if they don't exist"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Users table - PREMIUM with all features
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    bio TEXT,
                    location TEXT,
                    profile_picture_url TEXT,
                    first_seen_at TIMESTAMP DEFAULT NOW(),
                    last_active_at TIMESTAMP DEFAULT NOW(),
                    positive_votes INTEGER DEFAULT 0,
                    negative_votes INTEGER DEFAULT 0,
                    total_vouches INTEGER DEFAULT 0,
                    rating_percentage DECIMAL DEFAULT 100.0,
                    rank TEXT DEFAULT 'unverified',
                    streak_days INTEGER DEFAULT 0,
                    last_streak_date DATE,
                    referrer_id BIGINT
                )
            """)

            # Migrate existing databases to add new premium columns
            try:
                # Add all premium columns if they don't exist
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS location TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS positive_votes INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS negative_votes INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS total_vouches INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS rating_percentage DECIMAL DEFAULT 100.0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_days INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_streak_date DATE")

                # Dual-metric system columns
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS reputation_points DECIMAL DEFAULT 0.0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS behavior_points INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS behavior_rank TEXT DEFAULT 'new'")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_decay_date DATE")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS unique_vouchers INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS active_disputes INTEGER DEFAULT 0")

                # Starter Mode columns
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_starter_mode BOOLEAN DEFAULT TRUE")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS intro_message_id BIGINT")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS intro_endorsement_count INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS starter_unlock_at TIMESTAMP")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS bump_count INTEGER DEFAULT 0")
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_bump_at TIMESTAMP")

                # Migrate from old thumbs_up/down to new positive/negative votes if needed
                await conn.execute("""
                    UPDATE users
                    SET positive_votes = COALESCE(thumbs_up_count, 0),
                        negative_votes = COALESCE(thumbs_down_count, 0)
                    WHERE positive_votes = 0 AND negative_votes = 0
                """)

                # Drop old columns
                await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS thumbs_up_count")
                await conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS thumbs_down_count")
            except Exception as e:
                logger.warning(f"Schema migration warning (might be expected): {e}")

            # Vouches table - PREMIUM with edit history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS vouches (
                    id SERIAL PRIMARY KEY,
                    from_user_id BIGINT REFERENCES users(telegram_user_id),
                    to_user_id BIGINT REFERENCES users(telegram_user_id),
                    to_username TEXT,
                    message TEXT,
                    vote_type TEXT DEFAULT 'positive',
                    is_pending BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP
                )
            """)

            # Migrate existing vouches table
            try:
                # Add new premium columns
                await conn.execute("ALTER TABLE vouches ADD COLUMN IF NOT EXISTS to_username TEXT")
                await conn.execute("ALTER TABLE vouches ADD COLUMN IF NOT EXISTS is_pending BOOLEAN DEFAULT FALSE")
                await conn.execute("ALTER TABLE vouches ADD COLUMN IF NOT EXISTS vote_type TEXT DEFAULT 'positive'")
                await conn.execute("ALTER TABLE vouches ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")

                # Migrate from old is_thumbs_up to new vote_type if needed
                await conn.execute("""
                    UPDATE vouches
                    SET vote_type = CASE
                        WHEN is_thumbs_up = TRUE THEN 'positive'
                        ELSE 'negative'
                    END
                    WHERE vote_type IS NULL OR vote_type = ''
                """)

                # Drop old column
                await conn.execute("ALTER TABLE vouches DROP COLUMN IF EXISTS is_thumbs_up")
                await conn.execute("ALTER TABLE vouches DROP COLUMN IF EXISTS approved")
            except Exception as e:
                logger.warning(f"Vouches migration warning (might be expected): {e}")

            # Community Groups table - NEW for Groups tab
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS community_groups (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    telegram_link TEXT NOT NULL,
                    member_count INTEGER DEFAULT 0,
                    icon_emoji TEXT DEFAULT '💬',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Bot config table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Events/Analytics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    user_id BIGINT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Rank events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rank_events (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(telegram_user_id),
                    old_rank TEXT,
                    new_rank TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Invite tracking
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS invites (
                    id SERIAL PRIMARY KEY,
                    from_user_id BIGINT REFERENCES users(telegram_user_id),
                    to_username TEXT,
                    sent_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Disputes table - NEW for disputes system
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS disputes (
                    id SERIAL PRIMARY KEY,
                    reporter_id BIGINT REFERENCES users(telegram_user_id),
                    target_id BIGINT REFERENCES users(telegram_user_id),
                    evidence_url TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    admin_notes TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    reviewed_at TIMESTAMP,
                    review_deadline TIMESTAMP
                )
            """)

            # Behavior events table - NEW for behavior tracking
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS behavior_events (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(telegram_user_id),
                    event_type TEXT NOT NULL,
                    points_change INTEGER NOT NULL,
                    group_id BIGINT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_vouches_to_user ON vouches(to_user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_vouches_from_user ON vouches(from_user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)")

            logger.info("Database schema initialized successfully")

    # User operations
    async def get_or_create_user(self, telegram_user_id: int, username: Optional[str] = None,
                                  first_name: Optional[str] = None, last_name: Optional[str] = None,
                                  referrer_id: Optional[int] = None) -> Dict[str, Any]:
        """Get user or create if doesn't exist - SIMPLIFIED"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )

            if user:
                # Just update last active and username
                if username:
                    await conn.execute(
                        """UPDATE users SET
                           last_active_at = NOW(),
                           username = $2
                           WHERE telegram_user_id = $1""",
                        telegram_user_id, username
                    )
                else:
                    await conn.execute(
                        "UPDATE users SET last_active_at = NOW() WHERE telegram_user_id = $1",
                        telegram_user_id
                    )
                user_data = dict(user)
            else:
                # Create new user
                user = await conn.fetchrow("""
                    INSERT INTO users (telegram_user_id, username, first_name, last_name, referrer_id)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING *
                """, telegram_user_id, username, first_name, last_name, referrer_id)

                # Log signup event
                await self.log_event("user_signup", telegram_user_id, {
                    "referrer_id": referrer_id,
                    "username": username
                })

                user_data = dict(user)
            
            # Calculate total_vouches and rating if not set
            if user_data['total_vouches'] == 0:
                positive = user_data.get('positive_votes', 0)
                negative = user_data.get('negative_votes', 0)
                user_data['total_vouches'] = positive + negative

                # Calculate rating percentage
                if user_data['total_vouches'] > 0:
                    user_data['rating_percentage'] = (positive / user_data['total_vouches']) * 100
                else:
                    user_data['rating_percentage'] = 100.0

            return user_data

    async def get_user(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram ID"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )
            return dict(user) if user else None


    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all users with pagination"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            users = await conn.fetch(
                "SELECT * FROM users ORDER BY total_vouches DESC, positive_votes DESC LIMIT $1 OFFSET $2",
                limit, offset
            )
            return [dict(user) for user in users]

    async def update_user_rank(self, telegram_user_id: int, new_rank: str) -> None:
        """Update user rank and log event"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            old_rank = await conn.fetchval(
                "SELECT rank FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )

            await conn.execute(
                "UPDATE users SET rank = $1 WHERE telegram_user_id = $2",
                new_rank, telegram_user_id
            )

            # Log rank change event
            await conn.execute("""
                INSERT INTO rank_events (user_id, old_rank, new_rank)
                VALUES ($1, $2, $3)
            """, telegram_user_id, old_rank, new_rank)

            await self.log_event("rank_up", telegram_user_id, {
                "old_rank": old_rank,
                "new_rank": new_rank
            })

    # Vouch operations
    async def create_vouch(self, from_user_id: int, to_username: str, message: Optional[str] = None, vote_type: str = 'positive') -> Dict[str, Any]:
        """Create a new vouch with support for pending vouches"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Normalize username (case-insensitive, remove @)
            to_username = to_username.replace("@", "").lower().strip()

            if not to_username:
                return {"error": "Username is required"}

            # Find the user (case-insensitive)
            user = await conn.fetchrow(
                "SELECT telegram_user_id FROM users WHERE LOWER(username) = $1",
                to_username
            )

            if not user:
                # Create a pending vouch for user who hasn't joined yet
                vouch = await conn.fetchrow("""
                    INSERT INTO vouches (from_user_id, to_username, message, vote_type, is_pending)
                    VALUES ($1, $2, $3, $4, TRUE)
                    RETURNING *
                """, from_user_id, to_username, message, vote_type)

                await self.log_event("pending_vouch_created", from_user_id, {
                    "to_username": to_username,
                    "vote_type": vote_type
                })

                return {**dict(vouch), "pending": True}

            to_user_id = user["telegram_user_id"]

            # Check for self-vouch
            if to_user_id == from_user_id:
                return {"error": "You cannot vouch for yourself"}

            # Check if vouch already exists
            existing = await conn.fetchrow(
                "SELECT * FROM vouches WHERE from_user_id = $1 AND to_user_id = $2",
                from_user_id, to_user_id
            )

            if existing:
                return {"error": "You already vouched for this user"}

            # Create vouch
            vouch = await conn.fetchrow("""
                INSERT INTO vouches (from_user_id, to_user_id, message, vote_type, is_pending)
                VALUES ($1, $2, $3, $4, FALSE)
                RETURNING *
            """, from_user_id, to_user_id, message, vote_type)

            # Update cached counts and total
            if vote_type == 'positive':
                await conn.execute("""
                    UPDATE users
                    SET positive_votes = positive_votes + 1,
                        total_vouches = total_vouches + 1
                    WHERE telegram_user_id = $1
                """, to_user_id)
            else:
                await conn.execute("""
                    UPDATE users
                    SET negative_votes = negative_votes + 1,
                        total_vouches = total_vouches + 1
                    WHERE telegram_user_id = $1
                """, to_user_id)

            # Get updated counts and recalculate rank and rating
            counts = await conn.fetchrow(
                "SELECT positive_votes, negative_votes, total_vouches FROM users WHERE telegram_user_id = $1",
                to_user_id
            )

            # Calculate rating percentage
            rating_percentage = 100.0
            if counts['total_vouches'] > 0:
                rating_percentage = (counts['positive_votes'] / counts['total_vouches']) * 100

            await conn.execute(
                "UPDATE users SET rating_percentage = $1 WHERE telegram_user_id = $2",
                rating_percentage, to_user_id
            )

            # Update reputation with weighted vouching (NEW dual-metric system)
            await self.update_reputation(to_user_id, from_user_id, vote_type)

            new_rank = self.calculate_rank(counts['positive_votes'], counts['negative_votes'])
            current_rank = await conn.fetchval(
                "SELECT rank FROM users WHERE telegram_user_id = $1",
                to_user_id
            )

            if new_rank != current_rank:
                await self.update_user_rank(to_user_id, new_rank)

            # Check for mutual vouch
            mutual = await conn.fetchrow(
                "SELECT * FROM vouches WHERE from_user_id = $1 AND to_user_id = $2",
                to_user_id, from_user_id
            )

            if mutual:
                await self.log_event("mutual_vouch", from_user_id, {
                    "other_user": to_user_id
                })

            await self.log_event("vouch_created", from_user_id, {
                "to_user": to_user_id,
                "vote_type": vote_type
            })

            return {**dict(vouch), "pending": False, "mutual_vouch": bool(mutual)}

    async def update_vouch(self, vouch_id: int, from_user_id: int, new_message: str) -> Dict[str, Any]:
        """Update an existing vouch message - only the person who created it can edit"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Verify the vouch exists and belongs to the requesting user
            vouch = await conn.fetchrow(
                "SELECT * FROM vouches WHERE id = $1",
                vouch_id
            )

            if not vouch:
                return {"error": "Vouch not found"}

            if vouch["from_user_id"] != from_user_id:
                return {"error": "You can only edit your own vouches"}

            # Update the vouch message and set updated_at timestamp
            updated_vouch = await conn.fetchrow("""
                UPDATE vouches
                SET message = $1, updated_at = NOW()
                WHERE id = $2
                RETURNING *
            """, new_message, vouch_id)

            await self.log_event("vouch_updated", from_user_id, {
                "vouch_id": vouch_id,
                "to_user": vouch["to_user_id"]
            })

            return dict(updated_vouch)

    async def delete_vouch(self, vouch_id: int, from_user_id: int) -> Dict[str, Any]:
        """Delete a vouch - only the person who created it can delete"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Verify the vouch exists and belongs to the requesting user
            vouch = await conn.fetchrow(
                "SELECT * FROM vouches WHERE id = $1",
                vouch_id
            )

            if not vouch:
                return {"error": "Vouch not found"}

            if vouch["from_user_id"] != from_user_id:
                return {"error": "You can only delete your own vouches"}

            to_user_id = vouch["to_user_id"]
            vote_type = vouch["vote_type"]
            is_pending = vouch["is_pending"]

            # Delete the vouch
            await conn.execute(
                "DELETE FROM vouches WHERE id = $1",
                vouch_id
            )

            # Only update counts if vouch was not pending
            if not is_pending and to_user_id:
                # Update cached counts
                if vote_type == 'positive':
                    await conn.execute("""
                        UPDATE users
                        SET positive_votes = GREATEST(positive_votes - 1, 0),
                            total_vouches = GREATEST(total_vouches - 1, 0)
                        WHERE telegram_user_id = $1
                    """, to_user_id)
                else:
                    await conn.execute("""
                        UPDATE users
                        SET negative_votes = GREATEST(negative_votes - 1, 0),
                            total_vouches = GREATEST(total_vouches - 1, 0)
                        WHERE telegram_user_id = $1
                    """, to_user_id)

                # Recalculate rank and rating
                counts = await conn.fetchrow(
                    "SELECT positive_votes, negative_votes, total_vouches FROM users WHERE telegram_user_id = $1",
                    to_user_id
                )

                # Calculate rating percentage
                rating_percentage = 100.0
                if counts['total_vouches'] > 0:
                    rating_percentage = (counts['positive_votes'] / counts['total_vouches']) * 100

                new_rank = self.calculate_rank(counts['positive_votes'], counts['negative_votes'])

                await conn.execute("""
                    UPDATE users
                    SET rank = $1, rating_percentage = $2
                    WHERE telegram_user_id = $3
                """, new_rank, rating_percentage, to_user_id)

            await self.log_event("vouch_deleted", from_user_id, {
                "vouch_id": vouch_id,
                "to_user": to_user_id
            })

            return {"success": True}

    async def get_vouches_for_user(self, telegram_user_id: int) -> List[Dict[str, Any]]:
        """Get all vouches received by a user"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            vouches = await conn.fetch("""
                SELECT v.*, u.username, u.first_name, u.rank
                FROM vouches v
                JOIN users u ON v.from_user_id = u.telegram_user_id
                WHERE v.to_user_id = $1
                ORDER BY v.created_at DESC
            """, telegram_user_id)
            return [dict(vouch) for vouch in vouches]

    async def get_vouches_by_user(self, telegram_user_id: int) -> List[Dict[str, Any]]:
        """Get all vouches given by a user (including pending ones)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            vouches = await conn.fetch("""
                SELECT v.*, u.username, u.first_name, u.rank
                FROM vouches v
                LEFT JOIN users u ON v.to_user_id = u.telegram_user_id
                WHERE v.from_user_id = $1
                ORDER BY v.created_at DESC
            """, telegram_user_id)
            return [dict(vouch) for vouch in vouches]

    # Analytics operations
    async def log_event(self, event_type: str, user_id: Optional[int] = None, metadata: Optional[Dict] = None):
        """Log an analytics event"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Convert metadata dict to JSON string for JSONB column
            metadata_json = json.dumps(metadata) if metadata else None
            await conn.execute("""
                INSERT INTO events (event_type, user_id, metadata)
                VALUES ($1, $2, $3)
            """, event_type, user_id, metadata_json)

    async def get_analytics_summary(self) -> Dict[str, Any]:
        """Get analytics summary for dashboard"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Total users
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")

            # Active users (last 24h, 7d, 30d)
            active_24h = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE last_active_at > NOW() - INTERVAL '24 hours'"
            )
            active_7d = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE last_active_at > NOW() - INTERVAL '7 days'"
            )
            active_30d = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE last_active_at > NOW() - INTERVAL '30 days'"
            )

            # New signups (last 7 days)
            new_signups = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE first_seen_at > NOW() - INTERVAL '7 days'"
            )

            # Total vouches
            total_vouches = await conn.fetchval("SELECT COUNT(*) FROM vouches")

            # Rank distribution
            rank_dist = await conn.fetch(
                "SELECT rank, COUNT(*) as count FROM users GROUP BY rank"
            )

            # Top helpers (users who gave most vouches)
            top_helpers = await conn.fetch("""
                SELECT u.telegram_user_id, u.username, u.first_name, COUNT(v.id) as vouch_count
                FROM users u
                JOIN vouches v ON u.telegram_user_id = v.from_user_id
                WHERE v.created_at > NOW() - INTERVAL '7 days'
                GROUP BY u.telegram_user_id, u.username, u.first_name
                ORDER BY vouch_count DESC
                LIMIT 10
            """)

            # Most vouched users
            most_vouched = await conn.fetch("""
                SELECT telegram_user_id, username, first_name, thumbs_up_count, rank
                FROM users
                ORDER BY thumbs_up_count DESC
                LIMIT 10
            """)

            # Mutual vouch rate
            mutual_vouch_count = await conn.fetchval("""
                SELECT COUNT(*) FROM events WHERE event_type = 'mutual_vouch'
            """)

            return {
                "total_users": total_users,
                "active_users": {
                    "24h": active_24h,
                    "7d": active_7d,
                    "30d": active_30d
                },
                "new_signups_7d": new_signups,
                "total_vouches": total_vouches,
                "rank_distribution": [{"rank": r["rank"], "count": r["count"]} for r in rank_dist],
                "top_helpers": [dict(h) for h in top_helpers],
                "most_vouched": [dict(m) for m in most_vouched],
                "mutual_vouch_count": mutual_vouch_count
            }

    async def can_send_invite(self, from_user_id: int, to_username: str) -> bool:
        """Check if invite can be sent (rate limiting)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            recent_invite = await conn.fetchrow("""
                SELECT * FROM invites
                WHERE from_user_id = $1 AND to_username = $2
                AND sent_at > NOW() - INTERVAL '7 days'
            """, from_user_id, to_username)

            return recent_invite is None

    async def log_invite(self, from_user_id: int, to_username: str):
        """Log an invite sent"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO invites (from_user_id, to_username)
                VALUES ($1, $2)
            """, from_user_id, to_username)

    
    async def get_recent_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent activity feed (vouches and rank ups)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Get recent vouches
            recent_vouches = await conn.fetch("""
                SELECT 
                    'vouch' as activity_type,
                    v.created_at,
                    v.from_user_id,
                    v.to_user_id,
                    from_user.username as from_username,
                    from_user.first_name as from_first_name,
                    to_user.username as to_username,
                    to_user.first_name as to_first_name,
                    v.message
                FROM vouches v
                JOIN users from_user ON v.from_user_id = from_user.telegram_user_id
                LEFT JOIN users to_user ON v.to_user_id = to_user.telegram_user_id
                WHERE v.is_pending = FALSE
                ORDER BY v.created_at DESC
                LIMIT $1
            """, limit // 2)
            
            # Get recent rank ups
            recent_rankups = await conn.fetch("""
                SELECT 
                    'rank_up' as activity_type,
                    re.created_at,
                    re.user_id,
                    re.old_rank,
                    re.new_rank,
                    u.username,
                    u.first_name
                FROM rank_events re
                JOIN users u ON re.user_id = u.telegram_user_id
                ORDER BY re.created_at DESC
                LIMIT $1
            """, limit // 2)
            
            # Combine and sort by timestamp
            all_activity = [dict(v) for v in recent_vouches] + [dict(r) for r in recent_rankups]
            all_activity.sort(key=lambda x: x['created_at'], reverse=True)
            
            return all_activity[:limit]
    
    async def get_leaderboard(self, board_type: str = 'most_vouched', limit: int = 20) -> List[Dict[str, Any]]:
        """Get leaderboard data with different sorting options"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            if board_type == 'most_vouched':
                users = await conn.fetch("""
                    SELECT telegram_user_id, username, first_name, total_vouches, positive_votes, negative_votes, rank, streak_days, profile_picture_url
                    FROM users
                    ORDER BY total_vouches DESC, positive_votes DESC
                    LIMIT $1
                """, limit)
            elif board_type == 'top_givers':
                users = await conn.fetch("""
                    SELECT u.telegram_user_id, u.username, u.first_name, u.total_vouches, u.rank, u.streak_days, u.profile_picture_url,
                           COUNT(v.id) as vouches_given
                    FROM users u
                    LEFT JOIN vouches v ON u.telegram_user_id = v.from_user_id AND v.is_pending = FALSE
                    GROUP BY u.telegram_user_id
                    ORDER BY vouches_given DESC
                    LIMIT $1
                """, limit)
            elif board_type == 'rising_stars':
                # Users who gained vouches in the last 7 days
                users = await conn.fetch("""
                    SELECT u.telegram_user_id, u.username, u.first_name, u.total_vouches, u.rank, u.streak_days, u.profile_picture_url,
                           COUNT(v.id) as recent_vouches
                    FROM users u
                    LEFT JOIN vouches v ON u.telegram_user_id = v.to_user_id AND v.is_pending = FALSE
                    WHERE v.created_at > NOW() - INTERVAL '7 days'
                    GROUP BY u.telegram_user_id
                    HAVING COUNT(v.id) > 0
                    ORDER BY recent_vouches DESC
                    LIMIT $1
                """, limit)
            elif board_type == 'streak_leaders':
                users = await conn.fetch("""
                    SELECT telegram_user_id, username, first_name, total_vouches, rank, streak_days, profile_picture_url
                    FROM users
                    WHERE streak_days > 0
                    ORDER BY streak_days DESC
                    LIMIT $1
                """, limit)
            else:
                users = await conn.fetch("""
                    SELECT telegram_user_id, username, first_name, total_vouches, positive_votes, negative_votes, rank, streak_days, profile_picture_url
                    FROM users
                    ORDER BY total_vouches DESC
                    LIMIT $1
                """, limit)

            return [dict(u) for u in users]
    
    async def get_user_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """Get referral statistics for a user"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Count users who signed up via this user's referral
            referred_count = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE referrer_id = $1",
                user_id
            )

            # Get recent referrals
            recent_referrals = await conn.fetch("""
                SELECT telegram_user_id, username, first_name, first_seen_at, thumbs_up_count, rank
                FROM users
                WHERE referrer_id = $1
                ORDER BY first_seen_at DESC
                LIMIT 10
            """, user_id)

            return {
                "total_referrals": referred_count,
                "recent_referrals": [dict(r) for r in recent_referrals]
            }

    async def update_user_profile(self, telegram_user_id: int, bio: Optional[str] = None, location: Optional[str] = None, profile_picture_url: Optional[str] = None) -> Dict[str, Any]:
        """Update user profile information"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            updates = []
            values = []
            param_count = 1

            if bio is not None:
                updates.append(f"bio = ${param_count}")
                values.append(bio)
                param_count += 1

            if location is not None:
                updates.append(f"location = ${param_count}")
                values.append(location)
                param_count += 1

            if profile_picture_url is not None:
                updates.append(f"profile_picture_url = ${param_count}")
                values.append(profile_picture_url)
                param_count += 1

            if not updates:
                return {"error": "No fields to update"}

            values.append(telegram_user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_user_id = ${param_count} RETURNING *"

            user = await conn.fetchrow(query, *values)

            await self.log_event("profile_updated", telegram_user_id, {
                "bio": bio is not None,
                "location": location is not None,
                "photo": profile_picture_url is not None
            })

            return dict(user) if user else {"error": "User not found"}

    async def update_streak(self, telegram_user_id: int) -> Dict[str, Any]:
        """Update user's daily streak"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT streak_days, last_streak_date FROM users WHERE telegram_user_id = $1",
                telegram_user_id
            )

            if not user:
                return {"error": "User not found"}

            from datetime import date, timedelta
            today = date.today()
            last_streak = user['last_streak_date']

            if last_streak is None:
                # First streak
                new_streak = 1
            elif last_streak == today:
                # Already counted today
                return {"streak_days": user['streak_days'], "continued": False}
            elif last_streak == today - timedelta(days=1):
                # Consecutive day
                new_streak = user['streak_days'] + 1
            else:
                # Streak broken, restart
                new_streak = 1

            await conn.execute("""
                UPDATE users
                SET streak_days = $1, last_streak_date = $2
                WHERE telegram_user_id = $3
            """, new_streak, today, telegram_user_id)

            await self.log_event("streak_updated", telegram_user_id, {
                "streak_days": new_streak,
                "previous": user['streak_days']
            })

            return {"streak_days": new_streak, "continued": True}

    async def process_pending_vouches(self, telegram_user_id: int, username: str) -> int:
        """Process pending vouches when a user joins - PREMIUM feature"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Find all pending vouches for this username
            pending = await conn.fetch("""
                SELECT * FROM vouches
                WHERE LOWER(to_username) = $1 AND is_pending = TRUE
            """, username.lower())

            processed_count = 0

            for vouch in pending:
                # Update vouch to be confirmed
                await conn.execute("""
                    UPDATE vouches
                    SET to_user_id = $1, is_pending = FALSE
                    WHERE id = $2
                """, telegram_user_id, vouch['id'])

                # Update vote counts
                if vouch['vote_type'] == 'positive':
                    await conn.execute("""
                        UPDATE users
                        SET positive_votes = positive_votes + 1,
                            total_vouches = total_vouches + 1
                        WHERE telegram_user_id = $1
                    """, telegram_user_id)
                else:
                    await conn.execute("""
                        UPDATE users
                        SET negative_votes = negative_votes + 1,
                            total_vouches = total_vouches + 1
                        WHERE telegram_user_id = $1
                    """, telegram_user_id)

                processed_count += 1

            # Recalculate rank and rating if any vouches were processed
            if processed_count > 0:
                counts = await conn.fetchrow(
                    "SELECT positive_votes, negative_votes, total_vouches FROM users WHERE telegram_user_id = $1",
                    telegram_user_id
                )

                # Calculate rating percentage
                rating_percentage = 100.0
                if counts['total_vouches'] > 0:
                    rating_percentage = (counts['positive_votes'] / counts['total_vouches']) * 100

                new_rank = self.calculate_rank(counts['positive_votes'], counts['negative_votes'])

                await conn.execute("""
                    UPDATE users
                    SET rank = $1, rating_percentage = $2
                    WHERE telegram_user_id = $3
                """, new_rank, rating_percentage, telegram_user_id)

                await self.log_event("pending_vouches_processed", telegram_user_id, {
                    "count": processed_count
                })

            return processed_count

    # Community Groups operations
    async def get_community_groups(self) -> List[Dict[str, Any]]:
        """Get all community groups"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            groups = await conn.fetch("""
                SELECT * FROM community_groups
                ORDER BY member_count DESC, created_at DESC
            """)
            return [dict(g) for g in groups]

    async def add_community_group(self, name: str, telegram_link: str, description: Optional[str] = None,
                                   member_count: int = 0, icon_emoji: str = "💬") -> Dict[str, Any]:
        """Add a new community group (admin only)"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            group = await conn.fetchrow("""
                INSERT INTO community_groups (name, telegram_link, description, member_count, icon_emoji)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, name, telegram_link, description, member_count, icon_emoji)
            return dict(group)

    # Dual-Metric Reputation System
    async def update_reputation(self, user_id: int, voucher_id: int, vote_type: str) -> None:
        """Update reputation points with weighted vouching"""
        if vote_type != 'positive':
            return  # Only positive vouches add reputation

        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Get voucher's rank/tier
            voucher = await conn.fetchrow(
                "SELECT reputation_points FROM users WHERE telegram_user_id = $1",
                voucher_id
            )

            if not voucher:
                return

            # Calculate voucher's tier
            reputation_tier = self.calculate_reputation_tier(voucher['reputation_points'], 0)

            # Calculate weight
            weight = 0.0
            if reputation_tier == 'trusted':
                weight = 1.25
            elif reputation_tier == 'verified':
                weight = 1.0
            # Unverified vouchers add 0 reputation

            if weight > 0:
                # Update reputation points and unique vouchers count
                await conn.execute("""
                    UPDATE users
                    SET reputation_points = reputation_points + $1,
                        unique_vouchers = (
                            SELECT COUNT(DISTINCT from_user_id)
                            FROM vouches
                            WHERE to_user_id = $2 AND vote_type = 'positive' AND is_pending = FALSE
                        )
                    WHERE telegram_user_id = $2
                """, weight, user_id)

                # Get updated reputation and unique vouchers
                user_data = await conn.fetchrow(
                    "SELECT reputation_points, unique_vouchers, active_disputes FROM users WHERE telegram_user_id = $1",
                    user_id
                )

                # Calculate new reputation tier
                new_tier = self.calculate_reputation_tier(
                    user_data['reputation_points'],
                    user_data['unique_vouchers'],
                    user_data['active_disputes']
                )

                # Update rank column for compatibility
                await conn.execute(
                    "UPDATE users SET rank = $1 WHERE telegram_user_id = $2",
                    new_tier, user_id
                )

    async def record_behavior_event(self, user_id: int, event_type: str, points: int, group_id: Optional[int] = None) -> None:
        """Record a behavior event and update points with daily cap"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            # Check daily cap (+10 max per day)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            daily_points = await conn.fetchval("""
                SELECT COALESCE(SUM(points_change), 0)
                FROM behavior_events
                WHERE user_id = $1 AND created_at >= $2 AND points_change > 0
            """, user_id, today_start)

            # Apply daily cap
            if points > 0 and daily_points + points > 10:
                points = max(0, 10 - daily_points)

            if points != 0:
                # Record event
                await conn.execute("""
                    INSERT INTO behavior_events (user_id, event_type, points_change, group_id)
                    VALUES ($1, $2, $3, $4)
                """, user_id, event_type, points, group_id)

                # Update user's behavior points
                await conn.execute("""
                    UPDATE users
                    SET behavior_points = GREATEST(behavior_points + $1, 0)
                    WHERE telegram_user_id = $2
                """, points, user_id)

                # Get updated points and recalculate rank
                behavior_points = await conn.fetchval(
                    "SELECT behavior_points FROM users WHERE telegram_user_id = $1",
                    user_id
                )

                new_behavior_rank = self.calculate_behavior_rank(behavior_points)

                await conn.execute(
                    "UPDATE users SET behavior_rank = $1 WHERE telegram_user_id = $2",
                    new_behavior_rank, user_id
                )

    async def apply_monthly_decay(self, user_id: int) -> None:
        """Apply 10% monthly decay to behavior points"""
        pool = self._ensure_connected()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT behavior_points, last_decay_date FROM users WHERE telegram_user_id = $1",
                user_id
            )

            if not user:
                return

            # Check if a month has passed
            from datetime import date, timedelta
            today = date.today()
            last_decay = user['last_decay_date'] or today

            if (today - last_decay).days >= 30:
                # Apply 10% decay
                new_points = int(user['behavior_points'] * 0.9)

                await conn.execute("""
                    UPDATE users
                    SET behavior_points = $1,
                        last_decay_date = $2,
                        behavior_rank = $3
                    WHERE telegram_user_id = $4
                """, new_points, today, self.calculate_behavior_rank(new_points), user_id)

    @staticmethod
    def calculate_reputation_tier(reputation_points: float, unique_vouchers: int = 0, active_disputes: int = 0) -> str:
        """Calculate reputation tier based on weighted points"""
        # Unverified: < 3 rep points
        if reputation_points < 3.0:
            return "unverified"

        # Verified: >= 3 rep from 3 unique vouchers
        if reputation_points >= 3.0 and unique_vouchers >= 3:
            # Trusted: >= 7 rep from 5 unique + no active disputes
            if reputation_points >= 7.0 and unique_vouchers >= 5 and active_disputes == 0:
                return "trusted"
            return "verified"

        return "unverified"

    @staticmethod
    def calculate_behavior_rank(behavior_points: int) -> str:
        """Calculate behavior rank based on activity points"""
        if behavior_points >= 500:
            return "veteran"  # 🪙 Veteran (500+)
        elif behavior_points >= 200:
            return "contributor"  # 🔸 Contributor (200-499)
        elif behavior_points >= 50:
            return "active"  # 🔹 Active (50-199)
        else:
            return "new"  # 🧱 New (0-49)

    @staticmethod
    def get_behavior_rank_emoji(rank: str) -> str:
        """Get emoji for behavior rank"""
        emojis = {
            "new": "🧱",
            "active": "🔹",
            "contributor": "🔸",
            "veteran": "🪙"
        }
        return emojis.get(rank, "❓")

    @staticmethod
    def get_behavior_rank_name(rank: str) -> str:
        """Get display name for behavior rank"""
        names = {
            "new": "New",
            "active": "Active",
            "contributor": "Contributor",
            "veteran": "Veteran"
        }
        return names.get(rank, "Unknown")

    @staticmethod
    def calculate_rank(positive_votes: int, negative_votes: int) -> str:
        """Calculate rank based on positive/negative vouches - Premium 5-tier system"""
        total_votes = positive_votes + negative_votes

        # No vouches yet
        if total_votes == 0:
            return "unverified"

        # Calculate trust score (weighted by total volume)
        trust_ratio = positive_votes / total_votes if total_votes > 0 else 0

        # If too many negative votes, cap at verified even with high positive count
        if negative_votes >= 3 and trust_ratio < 0.8:
            return "verified"  # Can't advance with many negatives

        # Progressive rank system based on positive vouches and trust ratio
        if positive_votes >= 21 and trust_ratio >= 0.9:
            return "top_tier"
        elif positive_votes >= 11 and trust_ratio >= 0.85:
            return "endorsed"
        elif positive_votes >= 6 and trust_ratio >= 0.8:
            return "trusted"
        elif positive_votes >= 3 and trust_ratio >= 0.7:
            return "verified"
        else:
            return "unverified"

    @staticmethod
    def get_rank_emoji(rank: str) -> str:
        """Get emoji for rank"""
        rank_emojis = {
            "unverified": "🚫",
            "verified": "✅",
            "trusted": "🔷",
            "endorsed": "🛡",
            "top_tier": "👑"
        }
        return rank_emojis.get(rank, "❓")

    @staticmethod
    def get_rank_name(rank: str) -> str:
        """Get display name for rank"""
        rank_names = {
            "unverified": "Unverified",
            "verified": "Verified",
            "trusted": "Trusted",
            "endorsed": "Endorsed",
            "top_tier": "Top-Tier"
        }
        return rank_names.get(rank, "Unknown")

    @staticmethod
    def get_behavior_rank_emoji(behavior_rank: str) -> str:
        """Get emoji for behavior rank"""
        emojis = {
            "new": "🧱",
            "active": "🔹",
            "contributor": "🔸",
            "veteran": "🪙"
        }
        return emojis.get(behavior_rank, "🧱")

    @staticmethod
    def get_behavior_rank_name(behavior_rank: str) -> str:
        """Get display name for behavior rank"""
        names = {
            "new": "New",
            "active": "Active",
            "contributor": "Contributor",
            "veteran": "Veteran"
        }
        return names.get(behavior_rank, "New")

# Global database instance
db = Database()
