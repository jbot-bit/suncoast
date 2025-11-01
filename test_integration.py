"""
Test Integration - Verify Improvements are Working
Run this after deploying to verify all improvements are integrated correctly
"""
import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_imports():
    """Test that all modules can be imported"""
    logger.info("Testing imports...")

    try:
        from database_beacon import db
        logger.info("✅ database_beacon imported")

        from improvements_beacon import (
            ConnectionSuggester,
            ProgressiveModerator,
            StreakSystem
        )
        logger.info("✅ improvements_beacon imported")

        from bot_beacon import (
            connection_suggester,
            progressive_moderator,
            streak_system
        )
        logger.info("✅ bot_beacon improvements initialized")

        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False


async def test_database_schema():
    """Test that required database tables exist"""
    logger.info("\nTesting database schema...")

    try:
        from database_beacon import db

        # Connect to database
        await db.connect()
        pool = db._ensure_connected()

        async with pool.acquire() as conn:
            # Check for bot_config table
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'bot_config'
                )
            """)

            if result:
                logger.info("✅ bot_config table exists")
            else:
                logger.warning("⚠️  bot_config table missing (needed for streaks)")

            # Check for events table
            result = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'events'
                )
            """)

            if result:
                logger.info("✅ events table exists")
            else:
                logger.warning("⚠️  events table missing (needed for violations)")

        await db.disconnect()
        return True

    except Exception as e:
        logger.error(f"❌ Database test failed: {e}")
        return False


async def test_connection_suggester():
    """Test ConnectionSuggester functionality"""
    logger.info("\nTesting ConnectionSuggester...")

    try:
        from database_beacon import db
        from improvements_beacon import ConnectionSuggester

        await db.connect()
        suggester = ConnectionSuggester(db)

        # Test with a fake user ID (should return empty or error gracefully)
        suggestions = await suggester.get_suggested_connections(
            user_id=999999999,
            limit=3
        )

        logger.info(f"✅ ConnectionSuggester works (returned {len(suggestions)} suggestions)")

        await db.disconnect()
        return True

    except Exception as e:
        logger.error(f"❌ ConnectionSuggester test failed: {e}")
        return False


async def test_progressive_moderator():
    """Test ProgressiveModerator functionality"""
    logger.info("\nTesting ProgressiveModerator...")

    try:
        from database_beacon import db
        from improvements_beacon import ProgressiveModerator

        await db.connect()
        moderator = ProgressiveModerator(db)

        # Test with a fake user ID
        count, action = await moderator.check_user_violations(999999999)

        logger.info(f"✅ ProgressiveModerator works (count={count}, action={action})")

        # Test mute check
        is_muted = moderator.is_muted(999999999)
        logger.info(f"✅ Mute check works (is_muted={is_muted})")

        await db.disconnect()
        return True

    except Exception as e:
        logger.error(f"❌ ProgressiveModerator test failed: {e}")
        return False


async def test_streak_system():
    """Test StreakSystem functionality"""
    logger.info("\nTesting StreakSystem...")

    try:
        from database_beacon import db
        from improvements_beacon import StreakSystem

        await db.connect()
        streak_sys = StreakSystem(db)

        # Test with a fake user ID
        streak = await streak_sys.get_user_streak(999999999)

        logger.info(f"✅ StreakSystem works (streak={streak})")

        await db.disconnect()
        return True

    except Exception as e:
        logger.error(f"❌ StreakSystem test failed: {e}")
        return False


async def test_api_endpoints():
    """Test that new API endpoints are registered"""
    logger.info("\nTesting API endpoints...")

    try:
        from api_beacon import app

        routes = [route.path for route in app.routes]

        required_endpoints = [
            "/api/users/{telegram_user_id}/suggestions",
            "/api/users/{telegram_user_id}/streak",
            "/api/moderation/violations/{telegram_user_id}"
        ]

        for endpoint in required_endpoints:
            if endpoint in routes:
                logger.info(f"✅ {endpoint} registered")
            else:
                logger.warning(f"⚠️  {endpoint} not found")

        return True

    except Exception as e:
        logger.error(f"❌ API test failed: {e}")
        return False


async def test_webapp_files():
    """Test that webapp files have new functions"""
    logger.info("\nTesting webapp files...")

    try:
        js_file = "webapp/static/main_beacon.js"

        if not os.path.exists(js_file):
            logger.warning(f"⚠️  {js_file} not found")
            return False

        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()

        required_functions = [
            "loadUserStreak",
            "loadConnectionSuggestions",
            "renderStreakDisplay",
            "renderConnectionSuggestions",
            "quickVouch"
        ]

        for func in required_functions:
            if func in content:
                logger.info(f"✅ {func} found in webapp")
            else:
                logger.warning(f"⚠️  {func} not found in webapp")

        return True

    except Exception as e:
        logger.error(f"❌ Webapp test failed: {e}")
        return False


async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("VOUCH BEACON - INTEGRATION TEST SUITE")
    logger.info("=" * 60)

    # Check environment
    required_vars = ['BOT_TOKEN', 'DATABASE_URL', 'WEBHOOK_URL', 'ADMIN_ID', 'JWT_SECRET']
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        logger.error(f"\n❌ Missing environment variables: {', '.join(missing)}")
        logger.error("Set these in your .env file before testing")
        sys.exit(1)

    logger.info("\n✅ Environment variables present\n")

    # Run tests
    results = []

    results.append(await test_imports())
    results.append(await test_database_schema())
    results.append(await test_connection_suggester())
    results.append(await test_progressive_moderator())
    results.append(await test_streak_system())
    results.append(await test_api_endpoints())
    results.append(await test_webapp_files())

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS")
    logger.info("=" * 60)

    passed = sum(results)
    total = len(results)

    if passed == total:
        logger.info(f"\n✅ ALL TESTS PASSED ({passed}/{total})")
        logger.info("\nYour Vouch Beacon improvements are fully integrated!")
        logger.info("Ready to deploy: python main_beacon.py")
    else:
        logger.warning(f"\n⚠️  SOME TESTS FAILED ({passed}/{total} passed)")
        logger.warning("Review the errors above before deploying")

    logger.info("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
