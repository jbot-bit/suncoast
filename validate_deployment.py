"""
Deployment Validation - Vouch Portal Premium
Checks all components are ready for production deployment
"""
import sys
import os
import json

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"{GREEN}[OK]{RESET} {description}")
        return True
    else:
        print(f"{RED}[MISSING]{RESET} {description} - {filepath}")
        return False

def check_file_contains(filepath, search_text, description):
    """Check if file contains specific text"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if search_text in content:
                print(f"{GREEN}[OK]{RESET} {description}")
                return True
            else:
                print(f"{RED}[FAIL]{RESET} {description}")
                return False
    except Exception as e:
        print(f"{RED}[ERROR]{RESET} {description} - {e}")
        return False

def validate_deployment():
    """Run all deployment validation checks"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}  VOUCH PORTAL - DEPLOYMENT READINESS CHECK{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

    checks_passed = 0
    checks_total = 0

    # Section 1: Core Files
    print(f"\n{BLUE}[1/7] CORE FILES{RESET}")
    print("-" * 70)

    files = [
        ("main.py", "FastAPI application"),
        ("bot.py", "Telegram bot"),
        ("database.py", "Database layer"),
        ("requirements.txt", "Python dependencies")
    ]

    for filepath, desc in files:
        checks_total += 1
        if check_file_exists(filepath, desc):
            checks_passed += 1

    # Section 2: WebApp Files
    print(f"\n{BLUE}[2/7] WEBAPP FILES{RESET}")
    print("-" * 70)

    webapp_files = [
        ("webapp/index.html", "Main HTML file"),
        ("webapp/static/styles.css", "CSS stylesheet"),
        ("webapp/static/main.js", "JavaScript application")
    ]

    for filepath, desc in webapp_files:
        checks_total += 1
        if check_file_exists(filepath, desc):
            checks_passed += 1

    # Section 3: Premium Features - Database
    print(f"\n{BLUE}[3/7] PREMIUM DATABASE FEATURES{RESET}")
    print("-" * 70)

    db_features = [
        ("database.py", "positive_votes", "Positive vote tracking"),
        ("database.py", "negative_votes", "Negative vote tracking"),
        ("database.py", "rating_percentage", "Rating percentage system"),
        ("database.py", "streak_days", "Daily streak tracking"),
        ("database.py", "is_pending", "Pending vouch system"),
        ("database.py", "community_groups", "Community groups table"),
        ("database.py", "vote_type", "Vote type (positive/negative)")
    ]

    for filepath, search, desc in db_features:
        checks_total += 1
        if check_file_contains(filepath, search, desc):
            checks_passed += 1

    # Section 4: Premium Features - API
    print(f"\n{BLUE}[4/7] PREMIUM API ENDPOINTS{RESET}")
    print("-" * 70)

    api_features = [
        ("main.py", "@app.post(\"/api/vouch\")", "Vouch endpoint"),
        ("main.py", "@app.put(\"/api/profile\")", "Profile update endpoint"),
        ("main.py", "@app.post(\"/api/streak/update\")", "Streak update endpoint"),
        ("main.py", "@app.get(\"/api/pending-vouches", "Pending vouches endpoint"),
        ("main.py", "@app.get(\"/api/community-groups\")", "Community groups endpoint"),
        ("main.py", "vote_type", "Vote type parameter")
    ]

    for filepath, search, desc in api_features:
        checks_total += 1
        if check_file_contains(filepath, search, desc):
            checks_passed += 1

    # Section 5: Smart Moderation
    print(f"\n{BLUE}[5/7] SMART MODERATION SYSTEM{RESET}")
    print("-" * 70)

    moderation_features = [
        ("bot.py", "violation_tracker", "Violation tracking"),
        ("bot.py", "WARN_AFTER_STRIKES", "Strike threshold"),
        ("bot.py", "handle_violation_smartly", "Smart violation handling"),
        ("bot.py", "track_violation", "Violation tracker function")
    ]

    for filepath, search, desc in moderation_features:
        checks_total += 1
        if check_file_contains(filepath, search, desc):
            checks_passed += 1

    # Section 6: Professional Design
    print(f"\n{BLUE}[6/7] PROFESSIONAL DESIGN{RESET}")
    print("-" * 70)

    design_features = [
        ("webapp/static/styles.css", "--accent: #1d9bf0", "Twitter blue accent color"),
        ("webapp/static/styles.css", ".groups-grid", "Groups grid styling"),
        ("webapp/static/styles.css", ".rating-display", "Rating display styling"),
        ("webapp/index.html", "id=\"groupsView\"", "Groups view tab"),
        ("webapp/index.html", "id=\"ratingDisplay\"", "Rating display element"),
        ("webapp/index.html", "id=\"streakCount\"", "Streak counter element")
    ]

    for filepath, search, desc in design_features:
        checks_total += 1
        if check_file_contains(filepath, search, desc):
            checks_passed += 1

    # Section 7: No Gimmicks
    print(f"\n{BLUE}[7/7] NO GIMMICKY FEATURES{RESET}")
    print("-" * 70)

    # Check for absence of confetti
    checks_total += 1
    try:
        with open("webapp/static/main.js", 'r', encoding='utf-8') as f:
            content = f.read()
            if 'confetti({' not in content:
                print(f"{GREEN}[OK]{RESET} No confetti animations in JavaScript")
                checks_passed += 1
            else:
                print(f"{RED}[FAIL]{RESET} Confetti code found (should be removed)")
    except:
        print(f"{RED}[ERROR]{RESET} Could not check JavaScript file")

    checks_total += 1
    try:
        with open("webapp/index.html", 'r', encoding='utf-8') as f:
            content = f.read()
            if 'canvas-confetti' not in content:
                print(f"{GREEN}[OK]{RESET} No confetti library in HTML")
                checks_passed += 1
            else:
                print(f"{RED}[FAIL]{RESET} Confetti library found (should be removed)")
    except:
        print(f"{RED}[ERROR]{RESET} Could not check HTML file")

    # Summary
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}  VALIDATION SUMMARY{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")

    success_rate = (checks_passed / checks_total * 100) if checks_total > 0 else 0

    print(f"\nChecks Passed:  {GREEN}{checks_passed}{RESET}/{checks_total}")
    print(f"Success Rate:   {BLUE}{success_rate:.1f}%{RESET}")

    if checks_passed == checks_total:
        print(f"\n{GREEN}{'='*70}")
        print(f"  STATUS: READY FOR DEPLOYMENT")
        print(f"  All premium features implemented and verified")
        print(f"{'='*70}{RESET}\n")

        print(f"{BLUE}NEXT STEPS:{RESET}")
        print("1. Set up DATABASE_URL environment variable")
        print("2. Set up BOT_TOKEN environment variable")
        print("3. Set up ADMIN_ID environment variable")
        print("4. Run: python main.py")
        print("5. Configure Telegram bot webhook")
        print("6. Test in Telegram groups\n")

        return True
    else:
        failed = checks_total - checks_passed
        print(f"\n{YELLOW}{'='*70}")
        print(f"  STATUS: {failed} CHECK(S) FAILED")
        print(f"  Review failures above before deploying")
        print(f"{'='*70}{RESET}\n")
        return False

if __name__ == "__main__":
    try:
        success = validate_deployment()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n{RED}FATAL ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
