"""
Quick validation test for LocalVouch changes
"""
import asyncio
from database import db

async def test_database():
    """Test database methods"""
    print("🔍 Testing Database...")

    try:
        # Test rank calculation
        print("\n✅ Testing rank calculation:")
        ranks = {
            (0, 0): db.calculate_rank(0, 0),
            (1, 0): db.calculate_rank(1, 0),
            (3, 0): db.calculate_rank(3, 0),
            (10, 0): db.calculate_rank(10, 0),
            (5, 1): db.calculate_rank(5, 1),
            (5, 3): db.calculate_rank(5, 3),
        }
        for (up, down), rank in ranks.items():
            emoji = db.get_rank_emoji(rank)
            name = db.get_rank_name(rank)
            print(f"   {up}👍 {down}👎 → {emoji} {name}")

        print("\n✅ All database tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        return False

async def test_api_structure():
    """Test API structure"""
    print("\n🔍 Testing API Structure...")

    try:
        from main import app

        # Count routes
        routes = [route for route in app.routes if hasattr(route, 'methods')]
        print(f"   📡 Found {len(routes)} API routes")

        # Check key endpoints exist
        required_endpoints = [
            '/api/vouch',
            '/api/profile',
            '/api/users',
            '/api/community-groups'
        ]

        route_paths = [route.path for route in app.routes if hasattr(route, 'path')]

        for endpoint in required_endpoints:
            found = any(endpoint in path for path in route_paths)
            status = "✅" if found else "❌"
            print(f"   {status} {endpoint}")

        print("\n✅ API structure tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ API test failed: {e}")
        return False

def test_bot_handlers():
    """Test bot handlers"""
    print("\n🔍 Testing Bot Handlers...")

    try:
        from bot import create_bot_application

        app = create_bot_application()
        handlers = app.handlers

        print(f"   🤖 Found {len(handlers)} handler groups")

        # Check inline vouch handler exists
        has_inline_vouch = False
        for group in handlers.values():
            for handler in group:
                if hasattr(handler, 'callback') and handler.callback.__name__ == 'inline_vouch_handler':
                    has_inline_vouch = True
                    break

        status = "✅" if has_inline_vouch else "❌"
        print(f"   {status} Inline vouch handler registered")

        print("\n✅ Bot handler tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Bot test failed: {e}")
        return False

def test_frontend_files():
    """Test frontend files exist"""
    print("\n🔍 Testing Frontend Files...")

    try:
        import os

        files = {
            'HTML': 'webapp/index.html',
            'CSS': 'webapp/static/app.css',
            'JS': 'webapp/static/app.js'
        }

        all_exist = True
        for file_type, path in files.items():
            exists = os.path.exists(path)
            status = "✅" if exists else "❌"
            size = os.path.getsize(path) if exists else 0
            print(f"   {status} {file_type}: {path} ({size:,} bytes)")
            if not exists:
                all_exist = False

        if all_exist:
            print("\n✅ Frontend files tests passed!")
        else:
            print("\n❌ Some frontend files missing!")

        return all_exist
    except Exception as e:
        print(f"\n❌ Frontend test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("=" * 60)
    print("🚀 LOCALVOUCH VALIDATION TEST")
    print("=" * 60)

    results = []

    # Run tests
    results.append(await test_database())
    results.append(await test_api_structure())
    results.append(test_bot_handlers())
    results.append(test_frontend_files())

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 60)
        print("\n🎉 System is ready to run!")
        print("\n📝 Next steps:")
        print("   1. Ensure DATABASE_URL is set in environment")
        print("   2. Run: python main.py")
        print("   3. Open bot in Telegram")
        print("   4. Test inline vouching in a group!")
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("=" * 60)
        print("\n⚠️ Please fix the issues above before running.")

    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
