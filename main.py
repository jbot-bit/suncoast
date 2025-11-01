"""
FastAPI main application for Vouch Portal
Handles webhook, API endpoints, and serves the WebApp
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Update
from bot import create_bot_application, sanitize_message
from database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Global bot application
bot_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global bot_app

    # Startup
    logger.info("Starting Vouch Portal application...")

    # Connect to database
    await db.connect()

    # Initialize bot (allow app to start even if bot fails)
    try:
        bot_app = create_bot_application()
        await bot_app.initialize()
        await bot_app.start()
        
        # Set webhook if in production
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            try:
                # Ensure webhook URL ends with /webhook
                if not webhook_url.endswith("/webhook"):
                    webhook_url = f"{webhook_url}/webhook"
                
                await bot_app.bot.set_webhook(url=webhook_url)
                logger.info(f"Webhook set to: {webhook_url}")
                
                # Verify webhook was set
                webhook_info = await bot_app.bot.get_webhook_info()
                logger.info(f"Webhook status: URL={webhook_info.url}, Pending={webhook_info.pending_update_count}")
            except Exception as webhook_error:
                logger.error(f"Failed to set webhook: {webhook_error}")
        
        logger.info("Telegram bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        logger.warning("Application will continue without bot functionality")
        bot_app = None

    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    if bot_app:
        try:
            await bot_app.stop()
            await bot_app.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down bot: {e}")

    await db.disconnect()

    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Vouch Portal",
    description="Community trust and reputation system for Telegram",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static files
try:
    app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


# Pydantic models - PREMIUM
class VouchRequest(BaseModel):
    from_user_id: int
    to_username: str
    message: Optional[str] = None
    vote_type: str = "positive"  # "positive" or "negative"


class ProfileUpdateRequest(BaseModel):
    telegram_user_id: int
    bio: Optional[str] = None
    location: Optional[str] = None


class InviteRequest(BaseModel):
    from_user_id: int
    to_username: str


# Middleware to add no-cache headers for HTML, JS, and CSS
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """Add no-cache headers to prevent stale cached files"""
    response = await call_next(request)
    
    # Add no-cache headers for HTML, JS, and CSS files
    if (request.url.path == "/" or 
        request.url.path.endswith('.html') or 
        request.url.path.endswith('.js') or 
        request.url.path.endswith('.css')):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response


# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_webapp():
    """Serve the main WebApp"""
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Vouch Portal</h1><p>WebApp frontend not found. Please ensure webapp/index.html exists.</p>",
            status_code=200
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "vouch-portal",
        "database": "connected" if db.pool else "disconnected"
    }


@app.get("/api/bot-info")
async def get_bot_info():
    """Get bot configuration info"""
    return {
        "bot_username": os.getenv("BOT_USERNAME", "VouchPortalBot")
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Handle Telegram webhook updates"""
    logger.info("Webhook received a request")
    
    if not bot_app:
        logger.error("Bot not initialized")
        return {"status": "error", "message": "Bot not initialized"}
    
    try:
        data = await request.json()
        logger.info(f"Webhook data received: {data}")
        
        update = Update.de_json(data, bot_app.bot)
        logger.info(f"Update parsed: update_id={update.update_id if update else 'None'}")

        # Process update
        await bot_app.process_update(update)
        logger.info("Update processed successfully")

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@app.get("/api/users")
async def get_users(limit: int = 100, offset: int = 0):
    """Get list of all users"""
    try:
        users = await db.get_all_users(limit=limit, offset=offset)

        # Enhance with rank info
        for user in users:
            user["rank_emoji"] = db.get_rank_emoji(user["rank"])
            user["rank_name"] = db.get_rank_name(user["rank"])

            # Add behavior rank info (NEW dual-metric system)
            behavior_rank = user.get("behavior_rank", "new")
            user["behavior_rank_emoji"] = db.get_behavior_rank_emoji(behavior_rank)
            user["behavior_rank_name"] = db.get_behavior_rank_name(behavior_rank)

        return {"users": users}
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile/init")
async def initialize_user(request: Request):
    """Initialize or get user profile - auto-creates user if needed"""
    try:
        body = await request.json()
        telegram_user_id = body.get("telegram_user_id")
        username = body.get("username")
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        
        logger.info(f"Initializing profile for telegram_user_id: {telegram_user_id} (type: {type(telegram_user_id)}), username: {username}")
        
        if not telegram_user_id:
            logger.error("No telegram_user_id provided")
            raise HTTPException(status_code=400, detail="telegram_user_id is required")
        
        # Get or create user
        user = await db.get_or_create_user(
            telegram_user_id=telegram_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        return {"user": user, "created": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str):
    """Get user profile with vouches"""
    try:
        # Convert user_id to int, handling large numbers
        try:
            user_id_int = int(user_id)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid user_id format: {user_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        logger.info(f"Getting profile for user_id: {user_id_int} (original: {user_id}, type: {type(user_id)})")
        
        # Get user data
        user = await db.get_user(user_id_int)
        if not user:
            logger.warning(f"User not found: {user_id_int}")
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Found user: {user.get('username', 'no username')} with ID {user.get('telegram_user_id')}")

        # Get vouches
        vouches_received = await db.get_vouches_for_user(user_id_int)
        vouches_given = await db.get_vouches_by_user(user_id_int)

        # Add rank info (reputation tier)
        user["rank_emoji"] = db.get_rank_emoji(user["rank"])
        user["rank_name"] = db.get_rank_name(user["rank"])

        # Add behavior rank info (NEW dual-metric system)
        behavior_rank = user.get("behavior_rank", "new")
        user["behavior_rank_emoji"] = db.get_behavior_rank_emoji(behavior_rank)
        user["behavior_rank_name"] = db.get_behavior_rank_name(behavior_rank)

        # Calculate next rank info
        next_rank_threshold = 0
        if user["total_vouches"] < 3:
            next_rank_threshold = 3
        elif user["total_vouches"] < 6:
            next_rank_threshold = 6
        elif user["total_vouches"] < 11:
            next_rank_threshold = 11
        elif user["total_vouches"] < 16:
            next_rank_threshold = 16
        else:
            next_rank_threshold = user["total_vouches"]

        progress_percentage = 0
        if next_rank_threshold > 0 and user["total_vouches"] < 16:
            current_tier_start = 0
            if user["total_vouches"] >= 11:
                current_tier_start = 11
            elif user["total_vouches"] >= 6:
                current_tier_start = 6
            elif user["total_vouches"] >= 3:
                current_tier_start = 3

            progress_percentage = ((user["total_vouches"] - current_tier_start) /
                                   (next_rank_threshold - current_tier_start)) * 100

        return {
            "user": user,
            "vouches_received": vouches_received,
            "vouches_given": vouches_given,
            "next_rank_threshold": next_rank_threshold,
            "progress_percentage": min(100, max(0, progress_percentage))
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/vouch")
async def create_vouch(vouch_request: VouchRequest):
    """Create a new vouch - PREMIUM (supports pending vouches)"""
    try:
        # Validate vote_type
        if vouch_request.vote_type not in ["positive", "negative"]:
            raise HTTPException(status_code=400, detail="vote_type must be 'positive' or 'negative'")

        # Sanitize message (limit to 120 chars for premium)
        message = ""
        if vouch_request.message:
            message = sanitize_message(vouch_request.message)[:120]

        # Create vouch (supports pending vouches)
        target_username = vouch_request.to_username.replace("@", "").strip()
        result = await db.create_vouch(
            from_user_id=vouch_request.from_user_id,
            to_username=target_username,
            message=message if message else None,
            vote_type=vouch_request.vote_type
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # Get updated profile (if user exists)
        to_user_id = result.get("to_user_id")
        if to_user_id:
            profile = await get_profile(str(to_user_id))
            return {
                "success": True,
                "vouch": result,
                "profile": profile,
                "pending": False
            }
        else:
            # Pending vouch
            return {
                "success": True,
                "vouch": result,
                "pending": True,
                "message": f"Vouch for @{target_username} will be applied when they join!"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vouch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/vouches/{vouch_id}")
async def update_vouch(vouch_id: int, vouch_update: dict):
    """Update an existing vouch message - only the creator can edit"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        from_user_id = vouch_update.get("from_user_id")
        new_message = vouch_update.get("message", "")

        if not from_user_id:
            raise HTTPException(status_code=400, detail="from_user_id is required")

        # Sanitize the new message
        sanitized_message = sanitize_message(new_message) if new_message else ""

        # Update the vouch
        result = await db.update_vouch(vouch_id, from_user_id, sanitized_message)

        if "error" in result:
            # Return 404 if vouch not found, 403 if permission denied
            if result["error"] == "Vouch not found":
                raise HTTPException(status_code=404, detail=result["error"])
            else:
                raise HTTPException(status_code=403, detail=result["error"])

        return {
            "success": True,
            "vouch": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vouch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/vouches/{vouch_id}")
async def delete_vouch(vouch_id: int, vouch_delete: dict):
    """Delete a vouch - only the creator can delete"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        from_user_id = vouch_delete.get("from_user_id")

        if not from_user_id:
            raise HTTPException(status_code=400, detail="from_user_id is required")

        # Delete the vouch
        result = await db.delete_vouch(vouch_id, from_user_id)

        if "error" in result:
            # Return 404 if vouch not found, 403 if permission denied
            if result["error"] == "Vouch not found":
                raise HTTPException(status_code=404, detail=result["error"])
            else:
                raise HTTPException(status_code=403, detail=result["error"])

        return {
            "success": True,
            "message": "Vouch deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vouch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/profile")
async def update_profile(profile_update: ProfileUpdateRequest):
    """Update user profile (bio, location) - PREMIUM"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        # Sanitize inputs
        bio = sanitize_message(profile_update.bio)[:500] if profile_update.bio else None
        location = sanitize_message(profile_update.location)[:100] if profile_update.location else None

        # Update profile
        result = await db.update_user_profile(
            telegram_user_id=profile_update.telegram_user_id,
            bio=bio,
            location=location
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {
            "success": True,
            "user": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/streak/update")
async def update_streak(user_data: dict):
    """Update user's daily streak - PREMIUM"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        user_id = user_data.get("telegram_user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="telegram_user_id is required")

        # Update streak
        result = await db.update_streak(user_id)

        return {
            "success": True,
            "streak_days": result.get("streak_days", 0),
            "is_new_streak": result.get("is_new_streak", False)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating streak: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pending-vouches/{user_id}")
async def get_pending_vouches(user_id: int):
    """Get pending vouches for a user - PREMIUM"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db.pool.acquire() as conn:
            pending_vouches = await conn.fetch("""
                SELECT v.*, u.username as from_username, u.first_name
                FROM vouches v
                JOIN users u ON v.from_user_id = u.telegram_user_id
                WHERE v.to_user_id = $1 AND v.is_pending = TRUE
                ORDER BY v.created_at DESC
            """, user_id)

        return {
            "pending_vouches": [dict(v) for v in pending_vouches],
            "count": len(pending_vouches)
        }
    except Exception as e:
        logger.error(f"Error getting pending vouches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profile-photo/{user_id}")
async def fetch_profile_photo_file_id(user_id: int):
    """Fetch and cache user's Telegram profile photo file_id"""
    try:
        from bot import get_user_profile_photo_file_id
        
        # Check if we already have a cached file_id
        user = await db.get_user(user_id)
        if user and user.get("profile_picture_url"):
            # profile_picture_url now stores file_id
            return {
                "success": True,
                "file_id": user["profile_picture_url"],
                "cached": True
            }
        
        # Fetch from Telegram
        file_id = await get_user_profile_photo_file_id(user_id)
        
        if file_id:
            # Cache file_id in database (using profile_picture_url column)
            pool = db._ensure_connected()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET profile_picture_url = $1 WHERE telegram_user_id = $2",
                    file_id,
                    user_id
                )
            
            return {
                "success": True,
                "file_id": file_id,
                "cached": False
            }
        else:
            return {
                "success": False,
                "message": "No profile photo available"
            }
            
    except Exception as e:
        logger.error(f"Error fetching profile photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/photo-proxy/{file_id}")
async def proxy_profile_photo(file_id: str):
    """Proxy endpoint to serve Telegram profile photos without exposing bot token"""
    try:
        from bot import download_profile_photo_bytes
        from fastapi.responses import Response
        
        # Download photo bytes from Telegram
        photo_bytes = await download_profile_photo_bytes(file_id)
        
        if photo_bytes:
            # Return image with appropriate headers
            return Response(
                content=photo_bytes,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=86400"  # Cache for 24 hours
                }
            )
        else:
            raise HTTPException(status_code=404, detail="Photo not found")
            
    except Exception as e:
        logger.error(f"Error proxying profile photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/invite")
async def send_invite(invite_request: InviteRequest):
    """Send vouch invite to another user"""
    if not db.pool or not bot_app:
        raise HTTPException(status_code=503, detail="Service not available")
    
    try:
        # Check rate limit
        can_send = await db.can_send_invite(
            invite_request.from_user_id,
            invite_request.to_username.replace("@", "")
        )

        if not can_send:
            raise HTTPException(
                status_code=429,
                detail="You can only invite this user once per week"
            )

        # Log invite
        await db.log_invite(
            invite_request.from_user_id,
            invite_request.to_username.replace("@", "")
        )

        # Get inviter info
        inviter = await db.get_user(invite_request.from_user_id)

        # Send DM via bot (if user exists)
        try:
            async with db.pool.acquire() as conn:
                target_user = await conn.fetchrow(
                    "SELECT telegram_user_id FROM users WHERE username = $1",
                    invite_request.to_username.replace("@", "")
                )

            if target_user:
                # NOTIFICATIONS DISABLED - No invite messages sent
                # Just log the event without sending DM
                await db.log_event("invite_logged", invite_request.from_user_id, {
                    "to_username": invite_request.to_username
                })

                return {"success": True, "message": "Invite recorded"}
        except Exception as e:
            logger.error(f"Failed to send invite DM: {e}")
            # Log cooldown anyway
            await db.log_event("invite_cooldown_blocked", invite_request.from_user_id, {
                "to_username": invite_request.to_username
            })
            return {"success": True, "message": "Invite recorded (user not found on Telegram)"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending invite: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics")
async def get_analytics(user_id: Optional[int] = None):
    """Get analytics data (admin only or user-specific)"""
    try:
        # Get analytics summary
        analytics = await db.get_analytics_summary()

        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/activity")
async def get_activity(limit: int = 50):
    """Get recent community activity feed"""
    try:
        activity = await db.get_recent_activity(limit)
        return {"activity": activity}
    except Exception as e:
        logger.error(f"Error getting activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leaderboards/{board_type}")
async def get_leaderboard_by_type(board_type: str, limit: int = 20):
    """Get leaderboard data - supports: most_vouched, top_givers, rising_stars, streak_leaders"""
    try:
        leaderboard = await db.get_leaderboard(board_type, limit)
        
        # Add rank info
        for user in leaderboard:
            user["rank_emoji"] = db.get_rank_emoji(user["rank"])
            user["rank_name"] = db.get_rank_name(user["rank"])
        
        return {"leaderboard": leaderboard, "board_type": board_type}
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/referrals/{user_id}")
async def get_referral_stats(user_id: int):
    """Get referral statistics for a user"""
    try:
        stats = await db.get_user_referral_stats(user_id)

        # Add rank info
        for referral in stats["recent_referrals"]:
            referral["rank_emoji"] = db.get_rank_emoji(referral["rank"])
            referral["rank_name"] = db.get_rank_name(referral["rank"])

        return stats
    except Exception as e:
        logger.error(f"Error getting referral stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/community-groups")
async def get_community_groups():
    """Get all community groups for the Groups tab"""
    try:
        groups = await db.get_community_groups()
        return {"groups": groups}
    except Exception as e:
        logger.error(f"Error getting community groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/community-groups")
async def add_community_group(group_data: dict):
    """Add a new community group (admin only)"""
    try:
        # Simple admin check (you can enhance this)
        if group_data.get("admin_id") != ADMIN_ID:
            raise HTTPException(status_code=403, detail="Admin only")

        name = group_data.get("name")
        telegram_link = group_data.get("telegram_link")
        description = group_data.get("description")
        member_count = group_data.get("member_count", 0)
        icon_emoji = group_data.get("icon_emoji", "💬")

        if not name or not telegram_link:
            raise HTTPException(status_code=400, detail="Name and telegram_link are required")

        group = await db.add_community_group(name, telegram_link, description, member_count, icon_emoji)
        return {"success": True, "group": group}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding community group: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/viral/summary")
async def get_viral_summary():
    """Get viral growth summary"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with db.pool.acquire() as conn:
            # Vouches today
            vouches_today = await conn.fetchval("""
                SELECT COUNT(*) FROM vouches
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)

            # Referral stats
            referral_signups = await conn.fetchval("""
                SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL
            """)

            # Recent activity
            recent_vouches = await conn.fetch("""
                SELECT v.*, u1.username as from_username, u2.username as to_username
                FROM vouches v
                JOIN users u1 ON v.from_user_id = u1.telegram_user_id
                JOIN users u2 ON v.to_user_id = u2.telegram_user_id
                ORDER BY v.created_at DESC
                LIMIT 10
            """)

        return {
            "vouches_today": vouches_today,
            "referral_signups": referral_signups,
            "recent_activity": [dict(v) for v in recent_vouches]
        }
    except Exception as e:
        logger.error(f"Error getting viral summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_users(q: str, limit: int = 20):
    """Search users by username or name"""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        async with db.pool.acquire() as conn:
            users = await conn.fetch("""
                SELECT telegram_user_id, username, first_name, last_name, rank, total_vouches
                FROM users
                WHERE username ILIKE $1 OR first_name ILIKE $1 OR last_name ILIKE $1
                ORDER BY total_vouches DESC
                LIMIT $2
            """, f"%{q}%", limit)

        result_users = [dict(u) for u in users]

        # Add rank info
        for user in result_users:
            user["rank_emoji"] = db.get_rank_emoji(user["rank"])
            user["rank_name"] = db.get_rank_name(user["rank"])

        return {"results": result_users}
    except Exception as e:
        logger.error(f"Error searching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leaderboard")
async def get_leaderboard(period: str = "all"):
    """Get leaderboard data"""
    try:
        analytics = await db.get_analytics_summary()

        return {
            "most_vouched": analytics["most_vouched"],
            "top_helpers": analytics["top_helpers"]
        }
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/share")
async def log_share(user_id: int, platform: str):
    """Log share event"""
    try:
        await db.log_event("share_clicked", user_id, {"platform": platform})
        return {"success": True}
    except Exception as e:
        logger.error(f"Error logging share: {e}")
        return {"success": False}


# Admin endpoints
@app.get("/api/admin/config")
async def get_admin_config(admin_id: int):
    """Get admin configuration (admin only)"""
    if admin_id != ADMIN_ID:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db.pool.acquire() as conn:
            config = await conn.fetch("SELECT * FROM bot_config")

        return {"config": [dict(c) for c in config]}
    except Exception as e:
        logger.error(f"Error getting admin config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/config")
async def update_admin_config(admin_id: int, key: str, value: str):
    """Update admin configuration (admin only)"""
    if admin_id != ADMIN_ID:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO bot_config (key, value)
                VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
            """, key, value)

        return {"success": True}
    except Exception as e:
        logger.error(f"Error updating admin config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5000"))
    
    is_production = os.getenv("REPLIT_ENVIRONMENT", "development") == "production"
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=not is_production
    )
