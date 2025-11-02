"""
Vouch Beacon REST API
FastAPI endpoints for the Vouch Beacon ecosystem
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Update
from database_beacon import db

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
    logger.info("Starting Vouch Beacon application...")

    # Connect to database
    await db.connect()

    # Initialize bot
    try:
        from bot_beacon import create_bot_application
        bot_app = create_bot_application()
        await bot_app.initialize()
        await bot_app.start()
        logger.info("Telegram bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        logger.warning("Application will continue without bot functionality")
        bot_app = None

    logger.info("Vouch Beacon application started successfully")

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
    title="Vouch Beacon",
    description="Hybrid group-based vouch system with private actions, public recognition",
    version="2.0.0",
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


# Pydantic models
class VouchCreate(BaseModel):
    from_telegram_id: int
    to_username: str
    group_chat_id: Optional[int] = None
    comment: Optional[str] = None


class VouchUpdate(BaseModel):
    from_telegram_id: int
    comment: str


class VouchUndo(BaseModel):
    from_telegram_id: int


class MagicLinkRequest(BaseModel):
    telegram_user_id: int


# Middleware to add no-cache headers
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """Add no-cache headers to prevent stale cached files"""
    response = await call_next(request)

    if (request.url.path == "/" or
        request.url.path.endswith('.html') or
        request.url.path.endswith('.js') or
        request.url.path.endswith('.css')):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


# ==================== WEB APP ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def serve_webapp():
    """Serve the main WebApp"""
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Vouch Beacon</h1><p>WebApp frontend not found. Please ensure webapp/index.html exists.</p>",
            status_code=200
        )


@app.get("/auth")
async def magic_link_auth(token: str):
    """
    Magic Link authentication endpoint
    Verifies JWT token and sets session cookie
    """
    try:
        telegram_user_id = db.verify_magic_link(token)

        if not telegram_user_id:
            return HTMLResponse(
                content="<h1>Invalid or Expired Link</h1><p>This magic link has expired or is invalid. Please request a new one from the bot.</p>",
                status_code=400
            )

        # Get user data
        user = await db.get_user_by_telegram_id(telegram_user_id)
        if not user:
            return HTMLResponse(
                content="<h1>User Not Found</h1><p>Please connect with the bot first.</p>",
                status_code=404
            )

        # Redirect to profile with auth cookie
        response = RedirectResponse(url=f"/?user_id={telegram_user_id}")
        response.set_cookie(
            key="vouch_beacon_auth",
            value=token,
            httponly=True,
            max_age=900,  # 15 minutes
            samesite="lax"
        )

        return response

    except Exception as e:
        logger.error(f"Magic link auth error: {e}")
        return HTMLResponse(
            content=f"<h1>Error</h1><p>An error occurred: {str(e)}</p>",
            status_code=500
        )


# ==================== API ENDPOINTS ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "vouch-beacon",
        "database": "connected" if db.pool else "disconnected"
    }


@app.get("/api/bot-info")
async def get_bot_info():
    """Get bot configuration info"""
    return {
        "bot_username": os.getenv("BOT_USERNAME", "VouchBeaconBot")
    }


@app.post("/webhook")
async def webhook(request: Request):
    """Handle Telegram webhook updates"""
    if not bot_app:
        return {"status": "error", "message": "Bot not initialized"}

    try:
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)

        # Process update
        await bot_app.process_update(update)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


# ==================== VOUCH ENDPOINTS ====================

@app.post("/api/vouches")
async def create_vouch(vouch: VouchCreate):
    """
    Create a new vouch
    POST /api/vouches
    Body: {from_telegram_id, to_username, group_chat_id?, comment?}
    Returns: {vouch_id, to_user_telegram_id, created_at}
    """
    try:
        result = await db.create_vouch(
            from_telegram_id=vouch.from_telegram_id,
            to_username=vouch.to_username,
            group_chat_id=vouch.group_chat_id,
            comment=vouch.comment
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating vouch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/vouches/{vouch_id}")
async def update_vouch(vouch_id: int, vouch_update: VouchUpdate):
    """
    Update vouch comment
    PUT /vouches/{vouch_id}
    Body: {from_telegram_id, comment}
    """
    try:
        result = await db.update_vouch_comment(
            vouch_id=vouch_id,
            from_telegram_id=vouch_update.from_telegram_id,
            comment=vouch_update.comment
        )

        if "error" in result:
            if result["error"] == "Vouch not found":
                raise HTTPException(status_code=404, detail=result["error"])
            else:
                raise HTTPException(status_code=403, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vouch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/vouches/{vouch_id}")
async def undo_vouch(vouch_id: int, vouch_undo: VouchUndo):
    """
    Undo/soft delete a vouch
    DELETE /vouches/{vouch_id}
    Body: {from_telegram_id}
    """
    try:
        result = await db.undo_vouch(
            vouch_id=vouch_id,
            from_telegram_id=vouch_undo.from_telegram_id
        )

        if "error" in result:
            if result["error"] == "Vouch not found":
                raise HTTPException(status_code=404, detail=result["error"])
            else:
                raise HTTPException(status_code=403, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error undoing vouch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== USER ENDPOINTS ====================

@app.get("/api/users/{telegram_user_id}")
async def get_user_profile(telegram_user_id: int):
    """
    Get user profile with stats
    GET /users/{telegram_user_id}
    Returns: {user, vouches_received, vouches_given, vouches_received_list, vouches_given_list}
    """
    try:
        # Get user stats
        stats = await db.get_user_stats(telegram_user_id)

        if "error" in stats:
            raise HTTPException(status_code=404, detail=stats["error"])

        # Get recent vouches
        vouches_received_list = await db.get_vouches_for_user(telegram_user_id, limit=20)
        vouches_given_list = await db.get_vouches_by_user(telegram_user_id, limit=20)

        return {
            **stats,
            "vouches_received_list": vouches_received_list,
            "vouches_given_list": vouches_given_list
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEADERBOARD ENDPOINTS ====================

@app.get("/api/leaderboards")
async def get_leaderboards(type: str = "most_vouched", limit: int = 25):
    """
    Get leaderboard data
    GET /leaderboards?type=most_vouched&limit=25
    Types: most_vouched, top_givers
    """
    try:
        leaderboard = await db.get_leaderboard(board_type=type, limit=limit)
        return {
            "leaderboard": leaderboard,
            "type": type
        }
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== MAGIC LINK AUTHENTICATION ====================

@app.post("/api/auth/magic-link")
async def create_magic_link(request: MagicLinkRequest):
    """
    Generate magic link for user authentication
    POST /auth/magic-link
    Body: {telegram_user_id}
    Returns: {magic_link}
    """
    try:
        magic_link = db.generate_magic_link(request.telegram_user_id)
        return {"magic_link": magic_link}
    except Exception as e:
        logger.error(f"Error generating magic link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/analytics")
async def get_analytics():
    """Get analytics summary"""
    try:
        analytics = await db.get_analytics_summary()
        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== IMPROVEMENT ENDPOINTS ====================

@app.get("/api/users/{telegram_user_id}/suggestions")
async def get_connection_suggestions(telegram_user_id: int, limit: int = 5):
    """
    Get connection suggestions for a user
    GET /api/users/{telegram_user_id}/suggestions?limit=5
    Returns: List of suggested users to vouch for
    """
    try:
        from improvements_beacon import ConnectionSuggester
        suggester = ConnectionSuggester(db)
        suggestions = await suggester.get_suggested_connections(telegram_user_id, limit)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/{telegram_user_id}/streak")
async def get_user_streak(telegram_user_id: int):
    """
    Get user's current daily streak
    GET /api/users/{telegram_user_id}/streak
    Returns: {streak: int, last_active: datetime}
    """
    try:
        from improvements_beacon import StreakSystem
        streak_sys = StreakSystem(db)
        streak = await streak_sys.get_user_streak(telegram_user_id)
        user = await db.get_user_by_telegram_id(telegram_user_id)

        return {
            "streak": streak,
            "last_active": user['last_seen_at'].isoformat() if user else None
        }
    except Exception as e:
        logger.error(f"Error getting streak: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/moderation/violations/{telegram_user_id}")
async def get_user_violations(telegram_user_id: int):
    """
    Get violation count for a user (admin only)
    GET /api/moderation/violations/{telegram_user_id}
    Returns: {count: int, action: str}
    """
    try:
        from improvements_beacon import ProgressiveModerator
        moderator = ProgressiveModerator(db)
        count, action = await moderator.check_user_violations(telegram_user_id)

        return {
            "user_id": telegram_user_id,
            "violation_count": count,
            "next_action": action,
            "is_muted": moderator.is_muted(telegram_user_id)
        }
    except Exception as e:
        logger.error(f"Error getting violations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5000"))

    is_production = os.getenv("REPLIT_ENVIRONMENT", "development") == "production"

    uvicorn.run(
        "api_beacon:app",
        host="0.0.0.0",
        port=port,
        reload=not is_production
    )
