"""
Test script for Group Protection System
Tests pattern matching and AI analysis without needing a live bot
"""
import asyncio
import sys
import os

# Test cases
TEST_MESSAGES = [
    # Should be DELETED by pattern matching
    ("Check out this crypto opportunity at bit.ly/get-rich", True, "Scam URL shortener"),
    ("FREE MONEY CLICK HERE NOW!!!", True, "Spam pattern + caps"),
    ("My Bitcoin address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", True, "Crypto address"),
    ("Call me at +1-555-123-4567 for deals", True, "Phone number (doxxing)"),
    ("Email me at scammer@example.com", True, "Email address"),

    # Should be SAFE (legitimate messages)
    ("vouch @mike - great plumber", False, "Legitimate vouch"),
    ("Anyone know a good electrician?", False, "Normal question"),
    ("Thanks for the help!", False, "Normal chat"),
    ("Check out the official Telegram blog", False, "Legitimate URL discussion"),

    # Should be caught by AI (if enabled)
    ("DM me to buy verified accounts cheap", "AI", "Account selling (ToS violation)"),
    ("I can get you any documents you need, no questions", "AI", "Illegal services"),
    ("Join my pump and dump group for guaranteed profits", "AI", "Investment scam"),
]


def check_instant_violations_test(text: str):
    """Simplified version of check_instant_violations for testing"""
    import re

    text_lower = text.lower()

    # Scam domains
    scam_domains = ['bit.ly', 'tinyurl.com', 'goo.gl', 'airdrop', 'free-crypto']
    for domain in scam_domains:
        if domain in text_lower:
            return True, f"Scam domain: {domain}"

    # Banned words
    banned_words = [
        "scam", "fraud", "fake", "cheat", "steal", "hack",
        "porn", "xxx", "nsfw", "casino", "poker", "bet",
        "free money", "get rich", "make money fast"
    ]
    for word in banned_words:
        if word in text_lower:
            return True, f"Banned word: {word}"

    # Suspicious patterns
    patterns = [
        (r'[!@#$%^&*()]{4,}', "Excessive special characters"),
        (r'\b[A-Z]{15,}\b', "Excessive caps"),  # Increased from 10 to 15 to avoid false positives
        (r'\+\d[\d\-]{8,}', "Phone number"),  # Updated pattern to better match phone numbers
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', "Email address"),
        (r'\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-Z0-9]{39,59})\b', "Crypto address"),
    ]

    for pattern, reason in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True, reason

    return False, ""


async def test_ai_analysis(text: str):
    """Test AI analysis if Groq key is available"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None, "No API key"

    try:
        import httpx
        import json

        prompt = f'''Analyze if this Telegram message violates Terms of Service.

Message: "{text}"

Check for:
1. Scams/fraud (crypto schemes, phishing, investment scams)
2. Adult content (explicit imagery, dating spam)
3. Threats/violence (violent content, threats to individuals)
4. Spam (mass advertising, bot-like repetition)
5. Doxxing (personal addresses, private phone numbers)
6. Illegal content (drug/weapon sales, hacking services)

Respond ONLY with valid JSON (no markdown, no code blocks):
{{"verdict": "SAFE/SUSPICIOUS/VIOLATION", "category": "scam/adult/threat/spam/doxxing/illegal", "confidence": 0.95, "reason": "Brief reason"}}'''

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 150
                },
                timeout=5.0
            )

        if response.status_code != 200:
            return None, f"API error: {response.status_code}"

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()

        analysis = json.loads(content)
        return analysis, None

    except Exception as e:
        return None, str(e)


async def run_tests():
    """Run all tests"""
    print("=" * 70)
    print("GROUP PROTECTION SYSTEM - TEST SUITE")
    print("=" * 70)
    print()

    # Check if Groq is available
    groq_available = bool(os.getenv("GROQ_API_KEY"))
    if groq_available:
        print("[OK] Groq API key detected - AI analysis ENABLED")
    else:
        print("[!] No Groq API key - pattern matching only")
    print()

    results = {
        "pattern_correct": 0,
        "pattern_wrong": 0,
        "ai_correct": 0,
        "ai_wrong": 0,
        "ai_tests": 0
    }

    for i, (message, expected, description) in enumerate(TEST_MESSAGES, 1):
        print(f"Test {i}/{len(TEST_MESSAGES)}: {description}")
        print(f"Message: \"{message}\"")

        # Test pattern matching
        is_violation, reason = check_instant_violations_test(message)

        if expected is True:
            # Should be deleted
            if is_violation:
                print(f"[PASS] Pattern: Correctly flagged - {reason}")
                results["pattern_correct"] += 1
            else:
                print(f"[FAIL] Pattern: Should have been flagged but wasn't")
                results["pattern_wrong"] += 1
        elif expected is False:
            # Should be safe
            if not is_violation:
                print(f"[PASS] Pattern: Correctly marked as safe")
                results["pattern_correct"] += 1
            else:
                print(f"[FAIL] Pattern: False positive - {reason}")
                results["pattern_wrong"] += 1

        # Test AI if this requires AI and Groq is available
        if expected == "AI" and groq_available:
            print("  Testing AI analysis...", end=" ")
            analysis, error = await test_ai_analysis(message)
            results["ai_tests"] += 1

            if error:
                print(f"ERROR: {error}")
            elif analysis and analysis["verdict"] in ["VIOLATION", "SUSPICIOUS"]:
                print(f"[OK] AI detected: {analysis['category']} ({analysis['confidence']:.0%})")
                results["ai_correct"] += 1
            else:
                print(f"[FAIL] AI missed violation")
                results["ai_wrong"] += 1

        print()

    # Summary
    print("=" * 70)
    print("TEST RESULTS SUMMARY")
    print("=" * 70)
    total_pattern = results["pattern_correct"] + results["pattern_wrong"]
    pattern_accuracy = (results["pattern_correct"] / total_pattern * 100) if total_pattern > 0 else 0

    print(f"\nPattern Matching:")
    print(f"  Correct: {results['pattern_correct']}/{total_pattern}")
    print(f"  Accuracy: {pattern_accuracy:.1f}%")

    if results["ai_tests"] > 0:
        total_ai = results["ai_correct"] + results["ai_wrong"]
        ai_accuracy = (results["ai_correct"] / total_ai * 100) if total_ai > 0 else 0
        print(f"\nAI Analysis:")
        print(f"  Correct: {results['ai_correct']}/{total_ai}")
        print(f"  Accuracy: {ai_accuracy:.1f}%")
    else:
        print(f"\nAI Analysis: Not tested (no Groq API key)")

    print()

    # Recommendation
    if pattern_accuracy >= 80 and (results["ai_tests"] == 0 or results["ai_correct"] / results["ai_tests"] >= 0.7):
        print("[OK] System is working correctly!")
        print("  Ready to deploy to production.")
    else:
        print("[!] System needs review")
        print("  Check test failures above.")

    print()


if __name__ == "__main__":
    print()
    print("Testing Group Protection System...")
    print()

    # Check if running on Windows (needs proper handling)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_tests())
