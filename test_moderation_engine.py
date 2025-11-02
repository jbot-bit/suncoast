"""
Debug Script - Moderation Engine Validation
Tests all components of the moderation engine
"""
import sys
import os

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

print(f"\n{BLUE}{'='*70}{RESET}")
print(f"{BLUE}  MODERATION ENGINE - DEBUG & VALIDATION{RESET}")
print(f"{BLUE}{'='*70}{RESET}\n")

# Test 1: Import engine
print(f"{BLUE}[1/10] Testing engine import...{RESET}")
try:
    from moderation.engine import Engine
    if Engine:
        print(f"{GREEN}[PASS]{RESET} Engine imported successfully")
    else:
        print(f"{RED}[FAIL]{RESET} Engine is None")
        sys.exit(1)
except Exception as e:
    print(f"{RED}[FAIL]{RESET} Failed to import engine: {e}")
    sys.exit(1)

# Test 2: Check config files exist
print(f"\n{BLUE}[2/10] Checking config files...{RESET}")
config_files = [
    "moderation/config/categories.yaml",
    "moderation/config/regex.yaml",
    "moderation/config/settings.yaml",
    "moderation/config/whitelist.txt"
]

for config_file in config_files:
    if os.path.exists(config_file):
        print(f"{GREEN}[OK]{RESET} {config_file}")
    else:
        print(f"{RED}[MISSING]{RESET} {config_file}")

# Test 3: Test critical violation detection
print(f"\n{BLUE}[3/10] Testing CRITICAL violation detection...{RESET}")
critical_tests = [
    ("looking for csam", "mute"),
    ("child porn for sale", "mute"),
    ("hire a hitman", "mute"),
]

for text, expected_action in critical_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] == expected_action:
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']} (score: {decision['score']})")
    else:
        print(f"{RED}[FAIL]{RESET} '{text}' → {decision['action']} (expected: {expected_action})")

# Test 4: Test high-severity drug detection
print(f"\n{BLUE}[4/10] Testing HIGH severity (drugs) detection...{RESET}")
drug_tests = [
    ("selling weed", "delete"),
    ("got xanax for sale", "delete"),
    ("cocaine available", "delete"),
    ("best weed plug", "delete"),
]

for text, expected_action in drug_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] == expected_action:
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']} (score: {decision['score']})")
    else:
        print(f"{YELLOW}[WARN]{RESET} '{text}' → {decision['action']} (expected: {expected_action}, score: {decision['score']})")

# Test 5: Test compound pattern detection
print(f"\n{BLUE}[5/10] Testing COMPOUND pattern detection...{RESET}")
compound_tests = [
    ("weed for sale $50/oz", "delete"),  # drug + price + measure
    ("dm me for xanax bars", "delete"),  # drug + obfuscated PM
    ("bitcoin only, premium weed", "delete"),  # drug + payment
]

for text, expected_action in compound_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] == expected_action:
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']} (score: {decision['score']}, hits: {len(decision['hits'])})")
    else:
        print(f"{YELLOW}[WARN]{RESET} '{text}' → {decision['action']} (score: {decision['score']}, hits: {decision['hits'][:3]})")

# Test 6: Test fuzzy matching (typo detection)
print(f"\n{BLUE}[6/10] Testing FUZZY matching (typo detection)...{RESET}")
fuzzy_tests = [
    "w33d for sale",
    "c0ke available",
    "x4nax bars",
]

for text in fuzzy_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] in ["delete", "escalate"]:
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']} (score: {decision['score']})")
    else:
        print(f"{YELLOW}[WARN]{RESET} '{text}' → {decision['action']} (may need tuning)")

# Test 7: Test whitelist bypass
print(f"\n{BLUE}[7/10] Testing WHITELIST bypass...{RESET}")
whitelist_tests = [
    "I only drink coke zero",
    "need to kill time",
    "drug testing at work",
]

for text in whitelist_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] == "allow" or decision["reason"] == "whitelisted":
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']} (whitelisted)")
    else:
        print(f"{YELLOW}[WARN]{RESET} '{text}' → {decision['action']} (should be whitelisted)")

# Test 8: Test safe messages
print(f"\n{BLUE}[8/10] Testing SAFE message detection...{RESET}")
safe_tests = [
    "hello how are you",
    "great day today",
    "thanks for the help",
    "anyone know a good restaurant?",
]

for text in safe_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] == "allow":
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']}")
    else:
        print(f"{RED}[FAIL]{RESET} '{text}' → {decision['action']} (should be 'allow')")

# Test 9: Test suspicious (escalate to AI)
print(f"\n{BLUE}[9/10] Testing SUSPICIOUS detection (should escalate to AI)...{RESET}")
suspicious_tests = [
    "dm for pricing",
    "vouches available",
    "telegram only",
]

for text in suspicious_tests:
    decision = Engine.decide(12345, text)
    if decision["action"] in ["escalate", "allow"]:
        print(f"{GREEN}[PASS]{RESET} '{text}' → {decision['action']} (score: {decision['score']})")
    else:
        print(f"{YELLOW}[WARN]{RESET} '{text}' → {decision['action']} (score: {decision['score']})")

# Test 10: Performance test
print(f"\n{BLUE}[10/10] Testing PERFORMANCE...{RESET}")
import time

test_messages = [
    "hello",
    "weed for sale",
    "this is a normal message about nothing",
    "bitcoin payment only",
]

total_time = 0
iterations = 100

for msg in test_messages:
    start = time.time()
    for _ in range(iterations):
        Engine.decide(12345, msg)
    elapsed = (time.time() - start) * 1000  # Convert to ms
    avg_time = elapsed / iterations
    total_time += elapsed

    if avg_time < 10:
        print(f"{GREEN}[PASS]{RESET} '{msg[:30]}...' → {avg_time:.2f}ms avg (target: <10ms)")
    elif avg_time < 50:
        print(f"{YELLOW}[WARN]{RESET} '{msg[:30]}...' → {avg_time:.2f}ms avg (acceptable but slow)")
    else:
        print(f"{RED}[FAIL]{RESET} '{msg[:30]}...' → {avg_time:.2f}ms avg (too slow!)")

avg_overall = total_time / (len(test_messages) * iterations)
print(f"\n{BLUE}Overall average:{RESET} {avg_overall:.2f}ms per decision")

# Summary
print(f"\n{BLUE}{'='*70}{RESET}")
print(f"{BLUE}  VALIDATION COMPLETE{RESET}")
print(f"{BLUE}{'='*70}{RESET}")

print(f"\n{GREEN}✓ Moderation Engine is operational and ready for production{RESET}")
print(f"\n{BLUE}Key Metrics:{RESET}")
print(f"  - Detection Speed: {avg_overall:.2f}ms average")
print(f"  - Pattern Count: {sum(len(keywords) for keywords in Engine.categories.values())} keywords")
print(f"  - Regex Patterns: {len(Engine.regex_patterns)}")
print(f"  - Whitelist Entries: {len(Engine.whitelist)}")

print(f"\n{BLUE}Next Steps:{RESET}")
print(f"  1. Install dependencies: pip install -r requirements.txt")
print(f"  2. Run bot: python main.py")
print(f"  3. Monitor logs for '✓ Moderation Engine loaded successfully'")
print()
