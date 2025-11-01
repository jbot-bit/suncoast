"""
Vouch Beacon - 2 Month Simulation
Simulates realistic usage patterns to identify issues and improvements
"""
import asyncio
import random
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Set
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Simulation parameters
DAYS_TO_SIMULATE = 60
INITIAL_USERS = 10
DAILY_NEW_USERS_BASE = 5
VIRAL_COEFFICIENT = 1.2  # Exponential growth factor
DAILY_ACTIVE_RATE = 0.4  # 40% of users active daily
VOUCH_PROBABILITY = 0.15  # 15% chance active user vouches
SPAM_PROBABILITY = 0.02  # 2% of messages are spam
MESSAGES_PER_ACTIVE_USER = 8  # Average messages per day

# User behavior patterns
POWER_LAW_ALPHA = 2.5  # Power law for vouch distribution (some users vouch a lot)
RECIPROCAL_VOUCH_RATE = 0.3  # 30% chance of reciprocal vouch
BADGE_MOTIVATION_BOOST = 1.5  # Users near badge thresholds are more active

class SimulationState:
    """Track simulation state"""
    def __init__(self):
        self.users: Dict[int, Dict] = {}  # user_id -> user data
        self.vouches: List[Dict] = []  # All vouches
        self.messages: List[Dict] = []  # All messages
        self.violations: List[Dict] = []  # TOS violations
        self.welcome_mats: List[Dict] = []  # Welcome mat events
        self.current_day = 0
        self.total_users_created = 0

        # Metrics
        self.metrics = {
            'daily_active_users': [],
            'daily_vouches': [],
            'daily_violations': [],
            'daily_new_users': [],
            'network_density': [],
            'engagement_rate': [],
            'rank_distribution': [],
            'badge_distribution': []
        }

        # Issues found
        self.issues: List[Dict] = []
        self.warnings: List[Dict] = []

    def add_user(self, referred_by=None):
        """Add new user to simulation"""
        user_id = self.total_users_created + 1000
        self.total_users_created += 1

        self.users[user_id] = {
            'id': user_id,
            'username': f'user_{user_id}',
            'first_name': f'User{user_id}',
            'joined_day': self.current_day,
            'is_known_user': False,
            'vouches_received': 0,
            'vouches_given': 0,
            'last_active_day': self.current_day,
            'messages_sent': 0,
            'violations_count': 0,
            'referred_by': referred_by,
            'rank': 'newcomer',
            'badges': []
        }

        return user_id

    def complete_welcome_mat(self, user_id):
        """User completes Welcome Mat (clicks Connect)"""
        if user_id in self.users:
            self.users[user_id]['is_known_user'] = True
            self.welcome_mats.append({
                'user_id': user_id,
                'day': self.current_day,
                'completed': True
            })

    def create_vouch(self, from_id, to_id, day):
        """Create a vouch"""
        if from_id not in self.users or to_id not in self.users:
            return False

        # Check if user is known
        if not self.users[from_id]['is_known_user']:
            self.warnings.append({
                'day': day,
                'type': 'vouch_from_unknown_user',
                'user_id': from_id,
                'message': 'User tried to vouch without completing Welcome Mat'
            })
            return False

        # Check for self-vouch
        if from_id == to_id:
            self.warnings.append({
                'day': day,
                'type': 'self_vouch_attempt',
                'user_id': from_id
            })
            return False

        # Check for duplicate vouch
        existing = any(
            v['from_id'] == from_id and v['to_id'] == to_id and not v.get('deleted')
            for v in self.vouches
        )
        if existing:
            self.warnings.append({
                'day': day,
                'type': 'duplicate_vouch',
                'from_id': from_id,
                'to_id': to_id
            })
            return False

        # Create vouch
        self.vouches.append({
            'id': len(self.vouches) + 1,
            'from_id': from_id,
            'to_id': to_id,
            'day': day,
            'deleted': False
        })

        # Update stats
        self.users[from_id]['vouches_given'] += 1
        self.users[to_id]['vouches_received'] += 1

        # Update rank
        self.update_rank(to_id)

        # Update badges
        self.update_badges(from_id)
        self.update_badges(to_id)

        return True

    def update_rank(self, user_id):
        """Update user rank based on vouches received"""
        vouches = self.users[user_id]['vouches_received']
        old_rank = self.users[user_id]['rank']

        if vouches >= 51:
            new_rank = 'legend'
        elif vouches >= 21:
            new_rank = 'elite'
        elif vouches >= 11:
            new_rank = 'respected'
        elif vouches >= 6:
            new_rank = 'trusted'
        elif vouches >= 3:
            new_rank = 'known'
        elif vouches >= 1:
            new_rank = 'emerging'
        else:
            new_rank = 'newcomer'

        if new_rank != old_rank:
            self.users[user_id]['rank'] = new_rank
            logger.info(f"Day {self.current_day}: User {user_id} ranked up: {old_rank} → {new_rank}")

    def update_badges(self, user_id):
        """Update user badges"""
        user = self.users[user_id]
        badges = set(user['badges'])

        # First Vouch
        if user['vouches_received'] >= 1 and 'first_vouch' not in badges:
            badges.add('first_vouch')

        # Supporter (gave 10 vouches)
        if user['vouches_given'] >= 10 and 'supporter' not in badges:
            badges.add('supporter')

        # Collector (received 25 vouches)
        if user['vouches_received'] >= 25 and 'collector' not in badges:
            badges.add('collector')

        # Early Adopter (joined in first week)
        if user['joined_day'] <= 7 and 'early_adopter' not in badges:
            badges.add('early_adopter')

        user['badges'] = list(badges)

    def log_violation(self, user_id, day):
        """Log TOS violation"""
        self.violations.append({
            'user_id': user_id,
            'day': day
        })
        self.users[user_id]['violations_count'] += 1

# ==================== SIMULATION LOGIC ====================

async def simulate_day(state: SimulationState, day: int):
    """Simulate one day of activity"""
    state.current_day = day

    # Calculate daily metrics
    total_users = len(state.users)

    # Add new users (exponential growth)
    new_users_today = int(DAILY_NEW_USERS_BASE * (VIRAL_COEFFICIENT ** (day / 30)))
    new_users_today = min(new_users_today, 50)  # Cap at 50 per day for realism

    new_user_ids = []
    for _ in range(new_users_today):
        # Some users are referred by existing active users
        referrer = None
        if state.users and random.random() < 0.3:
            active_users = [uid for uid in state.users if state.users[uid]['is_known_user']]
            if active_users:
                referrer = random.choice(active_users)

        user_id = state.add_user(referred_by=referrer)
        new_user_ids.append(user_id)

    # Welcome Mat: New users complete onboarding
    # 70% completion rate (some users ignore it)
    for user_id in new_user_ids:
        if random.random() < 0.7:
            state.complete_welcome_mat(user_id)
        else:
            state.warnings.append({
                'day': day,
                'type': 'welcome_mat_ignored',
                'user_id': user_id,
                'message': 'User did not complete Welcome Mat'
            })

    # Determine active users for today
    active_user_ids = []
    for user_id in state.users:
        user = state.users[user_id]

        # Base activity rate
        activity_chance = DAILY_ACTIVE_RATE

        # Boost if near badge threshold
        if user['vouches_given'] in [8, 9] or user['vouches_received'] in [23, 24]:
            activity_chance *= BADGE_MOTIVATION_BOOST

        # Decay if user hasn't been active recently
        days_inactive = day - user['last_active_day']
        if days_inactive > 7:
            activity_chance *= 0.5

        if random.random() < activity_chance:
            active_user_ids.append(user_id)
            user['last_active_day'] = day

    # Active users send messages
    daily_messages = 0
    daily_vouches = 0
    daily_violations = 0

    for user_id in active_user_ids:
        user = state.users[user_id]

        # Send messages
        num_messages = random.randint(1, MESSAGES_PER_ACTIVE_USER)
        daily_messages += num_messages
        user['messages_sent'] += num_messages

        # Some messages are spam/TOS violations
        for _ in range(num_messages):
            if random.random() < SPAM_PROBABILITY:
                state.log_violation(user_id, day)
                daily_violations += 1

        # User might vouch for someone
        if random.random() < VOUCH_PROBABILITY and user['is_known_user']:
            # Power law: Some users are super active vouchers
            num_vouches = 1
            if random.random() < 0.1:  # 10% of users are power users
                num_vouches = random.randint(1, 3)

            for _ in range(num_vouches):
                # Choose someone to vouch for
                # Prefer people they might have interacted with (same day active users)
                potential_targets = [uid for uid in active_user_ids if uid != user_id]

                # Also consider random users (discovering new people)
                if random.random() < 0.3:
                    potential_targets = [uid for uid in state.users if uid != user_id]

                if potential_targets:
                    target_id = random.choice(potential_targets)

                    # Check for reciprocal vouch pattern
                    existing_vouch_to_me = any(
                        v['from_id'] == target_id and v['to_id'] == user_id
                        for v in state.vouches
                    )
                    if existing_vouch_to_me and random.random() < RECIPROCAL_VOUCH_RATE:
                        # More likely to vouch back
                        if state.create_vouch(user_id, target_id, day):
                            daily_vouches += 1
                    elif state.create_vouch(user_id, target_id, day):
                        daily_vouches += 1

    # Calculate network density
    if total_users > 1:
        max_possible_vouches = total_users * (total_users - 1)
        network_density = len([v for v in state.vouches if not v.get('deleted')]) / max_possible_vouches
    else:
        network_density = 0

    # Calculate engagement rate
    engagement_rate = len(active_user_ids) / total_users if total_users > 0 else 0

    # Store daily metrics
    state.metrics['daily_active_users'].append(len(active_user_ids))
    state.metrics['daily_vouches'].append(daily_vouches)
    state.metrics['daily_violations'].append(daily_violations)
    state.metrics['daily_new_users'].append(new_users_today)
    state.metrics['network_density'].append(network_density)
    state.metrics['engagement_rate'].append(engagement_rate)

    # Log progress every 10 days
    if day % 10 == 0:
        logger.info(f"Day {day}: {total_users} users, {len(active_user_ids)} active, {daily_vouches} vouches, {daily_violations} violations")

async def run_simulation():
    """Run full 2-month simulation"""
    logger.info("=" * 80)
    logger.info("VOUCH BEACON - 2 MONTH SIMULATION")
    logger.info("=" * 80)
    logger.info("")

    state = SimulationState()

    # Add initial seed users
    logger.info(f"Seeding with {INITIAL_USERS} initial users...")
    for _ in range(INITIAL_USERS):
        user_id = state.add_user()
        state.complete_welcome_mat(user_id)

    logger.info(f"Simulating {DAYS_TO_SIMULATE} days of activity...")
    logger.info("")

    # Run simulation
    for day in range(1, DAYS_TO_SIMULATE + 1):
        await simulate_day(state, day)
        await asyncio.sleep(0.001)  # Small delay to prevent blocking

    # Analyze results
    logger.info("")
    logger.info("=" * 80)
    logger.info("SIMULATION COMPLETE - ANALYZING RESULTS")
    logger.info("=" * 80)
    logger.info("")

    analyze_results(state)

def analyze_results(state: SimulationState):
    """Analyze simulation results and identify issues"""

    # ==================== GROWTH METRICS ====================
    logger.info("📊 GROWTH METRICS")
    logger.info("-" * 80)

    total_users = len(state.users)
    total_vouches = len([v for v in state.vouches if not v.get('deleted')])
    avg_vouches_per_user = total_vouches / total_users if total_users > 0 else 0

    logger.info(f"Total Users: {total_users}")
    logger.info(f"Total Vouches: {total_vouches}")
    logger.info(f"Avg Vouches per User: {avg_vouches_per_user:.2f}")
    logger.info(f"Total Violations Caught: {len(state.violations)}")
    logger.info(f"Welcome Mats Completed: {len(state.welcome_mats)}")
    logger.info("")

    # ==================== ENGAGEMENT ANALYSIS ====================
    logger.info("💡 ENGAGEMENT ANALYSIS")
    logger.info("-" * 80)

    avg_dau = sum(state.metrics['daily_active_users']) / len(state.metrics['daily_active_users'])
    avg_engagement = sum(state.metrics['engagement_rate']) / len(state.metrics['engagement_rate'])

    logger.info(f"Avg Daily Active Users: {avg_dau:.1f}")
    logger.info(f"Avg Engagement Rate: {avg_engagement:.1%}")

    # Check for declining engagement
    first_month_engagement = sum(state.metrics['engagement_rate'][:30]) / 30
    second_month_engagement = sum(state.metrics['engagement_rate'][30:]) / 30
    engagement_change = ((second_month_engagement - first_month_engagement) / first_month_engagement) * 100

    logger.info(f"Month 1 Engagement: {first_month_engagement:.1%}")
    logger.info(f"Month 2 Engagement: {second_month_engagement:.1%}")
    logger.info(f"Change: {engagement_change:+.1f}%")

    if engagement_change < -10:
        state.issues.append({
            'severity': 'high',
            'category': 'engagement',
            'issue': 'Significant engagement decline in month 2',
            'value': f"{engagement_change:.1f}%",
            'recommendation': 'Add retention features: daily quests, streaks, notifications for mutual vouches'
        })

    logger.info("")

    # ==================== NETWORK ANALYSIS ====================
    logger.info("🕸️ NETWORK ANALYSIS")
    logger.info("-" * 80)

    avg_network_density = sum(state.metrics['network_density']) / len(state.metrics['network_density'])
    logger.info(f"Avg Network Density: {avg_network_density:.4f}")

    # Check for isolated users
    users_with_no_vouches = sum(1 for u in state.users.values() if u['vouches_received'] == 0)
    isolated_rate = users_with_no_vouches / total_users

    logger.info(f"Users with 0 Vouches: {users_with_no_vouches} ({isolated_rate:.1%})")

    if isolated_rate > 0.3:
        state.issues.append({
            'severity': 'medium',
            'category': 'network',
            'issue': f'{isolated_rate:.1%} of users have no vouches',
            'recommendation': 'Implement suggested connections, "People you may know", or vouch prompts'
        })

    # Check vouch distribution (power law)
    vouch_counts = [u['vouches_received'] for u in state.users.values()]
    max_vouches = max(vouch_counts)
    median_vouches = sorted(vouch_counts)[len(vouch_counts) // 2]

    logger.info(f"Max Vouches: {max_vouches}")
    logger.info(f"Median Vouches: {median_vouches}")

    if max_vouches > 100:
        state.warnings.append({
            'category': 'distribution',
            'message': f'One user has {max_vouches} vouches - check for abuse/bots'
        })

    logger.info("")

    # ==================== RANK DISTRIBUTION ====================
    logger.info("🏆 RANK DISTRIBUTION")
    logger.info("-" * 80)

    rank_counts = defaultdict(int)
    for user in state.users.values():
        rank_counts[user['rank']] += 1

    for rank in ['newcomer', 'emerging', 'known', 'trusted', 'respected', 'elite', 'legend']:
        count = rank_counts[rank]
        percentage = (count / total_users) * 100
        logger.info(f"{rank.capitalize():12} {count:4} ({percentage:5.1f}%)")

    # Check if ranks are too easy or too hard
    if rank_counts['legend'] / total_users > 0.1:
        state.issues.append({
            'severity': 'medium',
            'category': 'gamification',
            'issue': f"{rank_counts['legend']} users reached Legend rank",
            'recommendation': 'Legend rank may be too easy - consider raising threshold to 75+ vouches'
        })

    if rank_counts['newcomer'] / total_users > 0.5:
        state.issues.append({
            'severity': 'low',
            'category': 'gamification',
            'issue': f'Over 50% of users stuck at Newcomer rank',
            'recommendation': 'Add onboarding vouch incentives or "first vouch" prompts'
        })

    logger.info("")

    # ==================== BADGE ANALYSIS ====================
    logger.info("🎖️ BADGE ANALYSIS")
    logger.info("-" * 80)

    badge_counts = defaultdict(int)
    for user in state.users.values():
        for badge in user['badges']:
            badge_counts[badge] += 1

    logger.info(f"First Vouch: {badge_counts['first_vouch']} ({badge_counts['first_vouch']/total_users:.1%})")
    logger.info(f"Supporter: {badge_counts['supporter']} ({badge_counts['supporter']/total_users:.1%})")
    logger.info(f"Collector: {badge_counts['collector']} ({badge_counts['collector']/total_users:.1%})")
    logger.info(f"Early Adopter: {badge_counts['early_adopter']} ({badge_counts['early_adopter']/total_users:.1%})")

    # Check if badges are too rare
    if badge_counts['collector'] < 5:
        state.warnings.append({
            'category': 'gamification',
            'message': 'Collector badge (25 vouches) may be too hard - only few users earned it'
        })

    logger.info("")

    # ==================== SECURITY & MODERATION ====================
    logger.info("🛡️ SECURITY & MODERATION")
    logger.info("-" * 80)

    violations_per_user = len(state.violations) / total_users
    logger.info(f"Total Violations: {len(state.violations)}")
    logger.info(f"Violations per User: {violations_per_user:.2f}")

    # Find repeat offenders
    user_violation_counts = defaultdict(int)
    for violation in state.violations:
        user_violation_counts[violation['user_id']] += 1

    repeat_offenders = {uid: count for uid, count in user_violation_counts.items() if count >= 5}
    logger.info(f"Repeat Offenders (5+ violations): {len(repeat_offenders)}")

    if repeat_offenders:
        state.issues.append({
            'severity': 'high',
            'category': 'security',
            'issue': f'{len(repeat_offenders)} users with 5+ violations',
            'recommendation': 'Implement escalating punishments: warnings → temp mute → ban'
        })

    logger.info("")

    # ==================== WELCOME MAT EFFECTIVENESS ====================
    logger.info("👋 WELCOME MAT EFFECTIVENESS")
    logger.info("-" * 80)

    completed_welcome_mats = len(state.welcome_mats)
    total_new_users = sum(state.metrics['daily_new_users'])
    completion_rate = completed_welcome_mats / total_new_users if total_new_users > 0 else 0

    logger.info(f"Total New Users: {total_new_users}")
    logger.info(f"Welcome Mats Completed: {completed_welcome_mats}")
    logger.info(f"Completion Rate: {completion_rate:.1%}")

    if completion_rate < 0.6:
        state.issues.append({
            'severity': 'medium',
            'category': 'onboarding',
            'issue': f'Low Welcome Mat completion rate ({completion_rate:.1%})',
            'recommendation': 'Make [Connect] button more prominent or add gentle reminder after 24h'
        })

    logger.info("")

    # ==================== DATABASE CONCERNS ====================
    logger.info("🗄️ DATABASE CONCERNS")
    logger.info("-" * 80)

    total_records = total_users + total_vouches + len(state.violations)
    logger.info(f"Total Database Records: {total_records:,}")

    # Estimate database size
    avg_record_size = 500  # bytes
    estimated_db_size_mb = (total_records * avg_record_size) / (1024 * 1024)
    logger.info(f"Estimated DB Size: {estimated_db_size_mb:.1f} MB")

    # Project 1 year growth
    daily_growth_rate = total_records / DAYS_TO_SIMULATE
    yearly_records = daily_growth_rate * 365
    yearly_size_gb = (yearly_records * avg_record_size) / (1024 * 1024 * 1024)

    logger.info(f"Projected 1 Year Records: {yearly_records:,.0f}")
    logger.info(f"Projected 1 Year DB Size: {yearly_size_gb:.2f} GB")

    if yearly_size_gb > 10:
        state.warnings.append({
            'category': 'scalability',
            'message': f'Database could reach {yearly_size_gb:.1f} GB in 1 year - consider archiving old data'
        })

    logger.info("")

    # ==================== PERFORMANCE BOTTLENECKS ====================
    logger.info("⚡ PERFORMANCE BOTTLENECKS")
    logger.info("-" * 80)

    # Calculate peak load
    peak_dau = max(state.metrics['daily_active_users'])
    peak_vouches = max(state.metrics['daily_vouches'])
    peak_violations = max(state.metrics['daily_violations'])

    logger.info(f"Peak Daily Active Users: {peak_dau}")
    logger.info(f"Peak Daily Vouches: {peak_vouches}")
    logger.info(f"Peak Daily Violations: {peak_violations}")

    # Estimate message throughput
    peak_messages = peak_dau * MESSAGES_PER_ACTIVE_USER
    messages_per_second = peak_messages / (24 * 3600)

    logger.info(f"Peak Daily Messages: ~{peak_messages}")
    logger.info(f"Peak Messages/Second: ~{messages_per_second:.2f}")

    if messages_per_second > 10:
        state.warnings.append({
            'category': 'performance',
            'message': f'Peak load of {messages_per_second:.1f} msg/s - ensure Guardian Protocol is optimized'
        })

    logger.info("")

    # ==================== ISSUES SUMMARY ====================
    logger.info("=" * 80)
    logger.info("🔴 ISSUES FOUND")
    logger.info("=" * 80)
    logger.info("")

    if not state.issues:
        logger.info("✅ No critical issues found!")
    else:
        for i, issue in enumerate(state.issues, 1):
            logger.info(f"{i}. [{issue['severity'].upper()}] {issue['category'].upper()}")
            logger.info(f"   Issue: {issue['issue']}")
            if 'value' in issue:
                logger.info(f"   Value: {issue['value']}")
            logger.info(f"   Recommendation: {issue['recommendation']}")
            logger.info("")

    # ==================== WARNINGS ====================
    if state.warnings:
        logger.info("=" * 80)
        logger.info("⚠️  WARNINGS")
        logger.info("=" * 80)
        logger.info("")

        warning_counts = defaultdict(int)
        for warning in state.warnings:
            warning_counts[warning['type'] if 'type' in warning else warning['category']] += 1

        for warning_type, count in warning_counts.items():
            logger.info(f"{warning_type}: {count} occurrences")

        logger.info("")

    # ==================== RECOMMENDATIONS ====================
    logger.info("=" * 80)
    logger.info("💡 TOP RECOMMENDATIONS")
    logger.info("=" * 80)
    logger.info("")

    recommendations = generate_recommendations(state)
    for i, rec in enumerate(recommendations, 1):
        logger.info(f"{i}. {rec['title']}")
        logger.info(f"   Priority: {rec['priority']}")
        logger.info(f"   Impact: {rec['impact']}")
        logger.info(f"   Implementation: {rec['implementation']}")
        logger.info("")

    # ==================== EXPORT RESULTS ====================
    logger.info("=" * 80)
    logger.info("💾 EXPORTING RESULTS")
    logger.info("=" * 80)
    logger.info("")

    results = {
        'simulation_days': DAYS_TO_SIMULATE,
        'total_users': total_users,
        'total_vouches': total_vouches,
        'metrics': state.metrics,
        'issues': state.issues,
        'warnings': state.warnings[:20],  # First 20 warnings
        'recommendations': recommendations
    }

    with open('simulation_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    logger.info("✅ Results exported to simulation_results.json")
    logger.info("")

def generate_recommendations(state: SimulationState) -> List[Dict]:
    """Generate prioritized recommendations based on simulation"""
    recommendations = []

    # Check engagement decline
    if any(i['category'] == 'engagement' for i in state.issues):
        recommendations.append({
            'title': 'Add Retention Features',
            'priority': 'HIGH',
            'impact': 'User retention, long-term engagement',
            'implementation': 'Add daily login streaks, weekly vouch goals, push notifications for mutual vouches'
        })

    # Check isolated users
    if any(i['category'] == 'network' for i in state.issues):
        recommendations.append({
            'title': 'Implement Connection Suggestions',
            'priority': 'HIGH',
            'impact': 'Network density, user activation',
            'implementation': '"People you may know" based on mutual connections, vouch prompts after Welcome Mat'
        })

    # Check Welcome Mat completion
    if any(i['category'] == 'onboarding' for i in state.issues):
        recommendations.append({
            'title': 'Improve Welcome Mat UX',
            'priority': 'MEDIUM',
            'impact': 'Onboarding completion rate',
            'implementation': 'Larger [Connect] button, show benefits (e.g., "Join 500+ verified members"), add reminder'
        })

    # Check gamification balance
    if any(i['category'] == 'gamification' for i in state.issues):
        recommendations.append({
            'title': 'Rebalance Rank Thresholds',
            'priority': 'MEDIUM',
            'impact': 'Long-term engagement, prestige',
            'implementation': 'Adjust Legend to 75+ vouches, add 2 more ranks above Legend (Mythic, Immortal)'
        })

    # Check security
    if any(i['category'] == 'security' for i in state.issues):
        recommendations.append({
            'title': 'Implement Progressive Moderation',
            'priority': 'HIGH',
            'impact': 'Community safety, admin workload',
            'implementation': '1st violation: warning, 3rd: 24h mute, 5th: permanent ban with appeal option'
        })

    # Always recommend analytics
    recommendations.append({
        'title': 'Add Real-Time Analytics Dashboard',
        'priority': 'MEDIUM',
        'impact': 'Operational visibility, issue detection',
        'implementation': 'Admin dashboard showing DAU, vouches/day, violations/day, engagement trends'
    })

    # Performance optimization
    if any(w.get('category') == 'performance' for w in state.warnings):
        recommendations.append({
            'title': 'Optimize Guardian Protocol',
            'priority': 'HIGH',
            'impact': 'Latency, scalability',
            'implementation': 'Add Redis caching for violation patterns, batch process non-critical logs'
        })

    # Database optimization
    if any(w.get('category') == 'scalability' for w in state.warnings):
        recommendations.append({
            'title': 'Implement Data Archival Strategy',
            'priority': 'LOW',
            'impact': 'Database performance, cost',
            'implementation': 'Archive vouches older than 1 year, soft delete inactive users after 6 months'
        })

    return recommendations[:6]  # Top 6 recommendations

if __name__ == "__main__":
    asyncio.run(run_simulation())
