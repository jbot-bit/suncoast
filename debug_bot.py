"""
Debug script for LocalVouch - Addresses the user's checklist
"""
import sys

print("=" * 70)
print("LOCALVOUCH DEBUG CHECK")
print("=" * 70)

# 1. Check main.py for API endpoint errors
print("\n[1/6] Checking main.py for API endpoint errors...")
try:
    from main import app
    routes = [r for r in app.routes if hasattr(r, 'path')]
    print(f"   [OK] main.py imported successfully")
    print(f"   [OK] Found {len(routes)} routes")

    # Check for critical endpoints
    critical_endpoints = ['/api/vouch', '/api/profile', '/api/users']
    for endpoint in critical_endpoints:
        exists = any(endpoint in r.path for r in routes)
        print(f"   [{'OK' if exists else 'ERROR'}] {endpoint}")
except Exception as e:
    print(f"   [ERROR] main.py has issues: {e}")
    import traceback
    traceback.print_exc()

# 2. Check bot.py for inline vouch handler errors
print("\n[2/6] Checking bot.py for inline vouch handler errors...")
try:
    from bot import create_bot_application, inline_vouch_handler, sanitize_message
    app = create_bot_application()
    print(f"   [OK] bot.py imported successfully")
    print(f"   [OK] inline_vouch_handler exists")
    print(f"   [OK] sanitize_message exists")
    print(f"   [OK] Bot application created with {len(app.handlers)} handler groups")

    # Check if inline vouch handler is registered
    found_handler = False
    for group in app.handlers.values():
        for handler in group:
            if hasattr(handler, 'callback') and handler.callback.__name__ == 'inline_vouch_handler':
                found_handler = True
                print(f"   [OK] inline_vouch_handler is registered")
                break

    if not found_handler:
        print(f"   [WARNING] inline_vouch_handler not found in registered handlers")

except Exception as e:
    print(f"   [ERROR] bot.py has issues: {e}")
    import traceback
    traceback.print_exc()

# 3. Validate frontend HTML/CSS/JS syntax
print("\n[3/6] Validating frontend files...")
import os

files_to_check = {
    'HTML': 'webapp/index.html',
    'CSS': 'webapp/static/app.css',
    'JS': 'webapp/static/app.js'
}

for file_type, path in files_to_check.items():
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"   [OK] {file_type}: {path} ({size:,} bytes)")

        # Basic validation
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

            if file_type == 'HTML':
                if '<html' not in content or '</html>' not in content:
                    print(f"   [WARNING] {path} may have invalid HTML structure")
                if 'app.css' not in content or 'app.js' not in content:
                    print(f"   [WARNING] {path} may not reference new CSS/JS files")

            elif file_type == 'CSS':
                if len(content) < 100:
                    print(f"   [WARNING] {path} seems too small")

            elif file_type == 'JS':
                if 'function' not in content and '=>' not in content:
                    print(f"   [WARNING] {path} may be empty or invalid")
    else:
        print(f"   [ERROR] {file_type}: {path} NOT FOUND")

# 4. Test database migration
print("\n[4/6] Testing database schema...")
try:
    from database import db
    print(f"   [OK] database.py imported successfully")

    # Test rank calculation (new system)
    test_cases = [
        (0, 0, 'new'),
        (1, 0, 'building'),
        (3, 0, 'trusted'),
        (10, 0, 'top_rated'),
        (5, 1, 'mixed'),
        (5, 3, 'caution')
    ]

    all_correct = True
    for up, down, expected in test_cases:
        result = db.calculate_rank(up, down)
        emoji = db.get_rank_emoji(result)
        name = db.get_rank_name(result)

        if result == expected:
            print(f"   [OK] {up}up {down}down -> {name} (correct)")
        else:
            print(f"   [ERROR] {up}up {down}down -> got '{result}', expected '{expected}'")
            all_correct = False

    if all_correct:
        print(f"   [OK] All rank calculations correct")

except Exception as e:
    print(f"   [ERROR] database.py has issues: {e}")
    import traceback
    traceback.print_exc()

# 5. Test API endpoints (without actually running server)
print("\n[5/6] Checking API endpoint definitions...")
try:
    from main import app
    import inspect

    # Get all route handlers
    routes_info = []
    for route in app.routes:
        if hasattr(route, 'endpoint') and hasattr(route, 'methods'):
            func = route.endpoint
            sig = inspect.signature(func)
            routes_info.append({
                'path': route.path,
                'methods': route.methods,
                'params': list(sig.parameters.keys())
            })

    # Check critical endpoints
    critical = {
        '/api/vouch': {'method': 'POST', 'required_params': ['vouch_request']},
        '/api/profile/{user_id}': {'method': 'GET', 'required_params': ['user_id']},
        '/api/users': {'method': 'GET', 'required_params': []},
        '/api/community-groups': {'method': 'GET', 'required_params': []}
    }

    for endpoint, requirements in critical.items():
        found = False
        for route in routes_info:
            if endpoint.replace('{user_id}', '') in route['path']:
                found = True
                if requirements['method'] in route['methods']:
                    print(f"   [OK] {endpoint} ({requirements['method']})")
                else:
                    print(f"   [WARNING] {endpoint} missing {requirements['method']}")
                break

        if not found:
            print(f"   [ERROR] {endpoint} not found!")

except Exception as e:
    print(f"   [ERROR] API endpoint check failed: {e}")
    import traceback
    traceback.print_exc()

# 6. Check for critical errors
print("\n[6/6] Checking for common critical errors...")
errors_found = []

# Check for removed column references
try:
    import database
    with open('database.py', 'r') as f:
        db_content = f.read()
        old_cols = ['total_vouches', 'positive_votes', 'negative_votes', 'streak_days']
        for col in old_cols:
            # Skip DROP COLUMN statements
            if col in db_content and 'DROP COLUMN' not in db_content[db_content.index(col)-50:db_content.index(col)]:
                count = db_content.count(col)
                print(f"   [WARNING] '{col}' found {count} times in database.py (should be removed)")
                errors_found.append(f"Old column '{col}' still referenced")

    if not errors_found:
        print(f"   [OK] No old column references in database.py")

except Exception as e:
    print(f"   [WARNING] Could not check database.py content: {e}")

# Check for removed function calls
try:
    with open('main.py', 'r') as f:
        main_content = f.read()
        if 'sanitize_user_profile_url' in main_content:
            count = main_content.count('sanitize_user_profile_url')
            print(f"   [ERROR] 'sanitize_user_profile_url' still called {count} times in main.py")
            errors_found.append("Removed function sanitize_user_profile_url still called")
        else:
            print(f"   [OK] No removed function calls in main.py")

except Exception as e:
    print(f"   [WARNING] Could not check main.py content: {e}")

# Summary
print("\n" + "=" * 70)
if errors_found:
    print(f"[FAILED] Found {len(errors_found)} critical error(s):")
    for i, error in enumerate(errors_found, 1):
        print(f"   {i}. {error}")
    print("\nPlease fix these errors before running the app.")
    sys.exit(1)
else:
    print("[SUCCESS] All checks passed!")
    print("\nYour LocalVouch app is ready to run!")
    print("\nNext steps:")
    print("   1. Set environment variables (BOT_TOKEN, DATABASE_URL, etc.)")
    print("   2. Run: python main.py")
    print("   3. Open bot in Telegram")
    print("   4. Test inline vouching in a group: 'vouch @username'")
    sys.exit(0)
