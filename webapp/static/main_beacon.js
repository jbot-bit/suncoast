// ==================== VOUCH BEACON MAIN SCRIPT ====================
// Professional engagement-optimized web app

// Configuration
const API_BASE = window.location.origin;
const tg = window.Telegram?.WebApp;

// State management
const state = {
    currentUser: null,
    currentTab: 'profile',
    leaderboardType: 'most_vouched',
    networkData: null
};

// Gamification system
const RANKS = [
    { level: 0, name: 'Newcomer', min: 0, max: 0, icon: '🆕', color: '#6B7280' },
    { level: 1, name: 'Emerging', min: 1, max: 2, icon: '🌱', color: '#10B981' },
    { level: 2, name: 'Known', min: 3, max: 5, icon: '⭐', color: '#3B82F6' },
    { level: 3, name: 'Trusted', min: 6, max: 10, icon: '✅', color: '#8B5CF6' },
    { level: 4, name: 'Respected', min: 11, max: 20, icon: '🏆', color: '#F59E0B' },
    { level: 5, name: 'Elite', min: 21, max: 50, icon: '💎', color: '#EF4444' },
    { level: 6, name: 'Legend', min: 51, max: Infinity, icon: '👑', color: '#FFD700' }
];

const BADGES = {
    first_vouch: { name: 'First Vouch', icon: '🎯', desc: 'Received your first vouch' },
    vouch_giver: { name: 'Supporter', icon: '🤝', desc: 'Gave 10 vouches' },
    vouch_collector: { name: 'Collector', icon: '📚', desc: 'Received 25 vouches' },
    early_adopter: { name: 'Early Adopter', icon: '🚀', desc: 'Joined in the first week' },
    influencer: { name: 'Influencer', icon: '🌟', desc: 'Network of 50+ connections' },
    trusted_circle: { name: 'Trusted Circle', icon: '🔒', desc: 'All vouches from verified users' }
};

// ==================== INITIALIZATION ====================

async function init() {
    try {
        // Initialize Telegram WebApp
        if (tg) {
            tg.ready();
            tg.expand();
            tg.setHeaderColor('#0A0E27');
            tg.setBackgroundColor('#0A0E27');
        }

        // Get user from Telegram WebApp or URL
        const userId = tg?.initDataUnsafe?.user?.id || getUserIdFromUrl();

        if (!userId) {
            showError('Unable to identify user. Please open from Telegram.');
            return;
        }

        // Load user profile
        await loadUserProfile(userId);

        // Setup event listeners
        setupEventListeners();

        // Hide loading, show app
        document.getElementById('loadingScreen').style.display = 'none';
        document.getElementById('app').style.display = 'block';

    } catch (error) {
        console.error('Initialization error:', error);
        showError('Failed to load app. Please try again.');
    }
}

function getUserIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get('user_id');
}

// ==================== USER PROFILE ====================

async function loadUserProfile(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/users/${userId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load profile');
        }

        state.currentUser = data;

        // Render profile
        renderProfile(data);
        renderVouchesReceived(data.vouches_received_list);
        renderVouchesGiven(data.vouches_given_list);

        // Load and display streak
        loadUserStreak(userId);

        // Load connection suggestions if isolated
        if (data.vouches_received === 0 && data.vouches_given === 0) {
            loadConnectionSuggestions(userId);
        }

    } catch (error) {
        console.error('Error loading profile:', error);
        showToast('Failed to load profile', 'error');
    }
}

async function loadUserStreak(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/users/${userId}/streak`);
        const data = await response.json();

        if (response.ok && data.streak > 0) {
            renderStreakDisplay(data.streak);
        }
    } catch (error) {
        console.error('Error loading streak:', error);
    }
}

async function loadConnectionSuggestions(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/users/${userId}/suggestions?limit=3`);
        const data = await response.json();

        if (response.ok && data.suggestions && data.suggestions.length > 0) {
            renderConnectionSuggestions(data.suggestions);
        }
    } catch (error) {
        console.error('Error loading suggestions:', error);
    }
}

function renderProfile(data) {
    const { user, vouches_received, vouches_given } = data;

    // Basic info
    document.getElementById('profileName').textContent = user.first_name || 'User';
    document.getElementById('profileUsername').textContent = `@${user.username || 'username'}`;

    // Stats
    document.getElementById('vouchesReceived').textContent = vouches_received;
    document.getElementById('vouchesGiven').textContent = vouches_given;
    document.getElementById('receivedCount').textContent = vouches_received;
    document.getElementById('givenCount').textContent = vouches_given;

    // Calculate rank
    const rank = calculateRank(vouches_received);
    renderRankBadge(rank, vouches_received);

    // Calculate and show badges
    const earnedBadges = calculateEarnedBadges(data);
    if (earnedBadges.length > 0) {
        renderBadges(earnedBadges);
    }
}

function calculateRank(vouchCount) {
    return RANKS.find(rank => vouchCount >= rank.min && vouchCount <= rank.max) || RANKS[0];
}

function renderRankBadge(rank, currentVouches) {
    const profileHero = document.querySelector('.profile-hero');

    // Remove existing rank display if any
    const existingRank = document.querySelector('.rank-display');
    if (existingRank) existingRank.remove();

    const rankDiv = document.createElement('div');
    rankDiv.className = 'rank-display';

    rankDiv.innerHTML = `
        <span style="font-size: 20px;">${rank.icon}</span>
        <span>${rank.name}</span>
        <span>Level ${rank.level}</span>
    `;

    // Insert after avatar
    const avatar = profileHero.querySelector('.profile-avatar-large');
    avatar.after(rankDiv);

    // Show progress to next rank
    const nextRank = RANKS[rank.level + 1];
    if (nextRank) {
        renderProgressBar(currentVouches, rank.max, nextRank);
    }
}

function renderProgressBar(current, currentMax, nextRank) {
    const profileHero = document.querySelector('.profile-hero');

    const existingProgress = document.querySelector('.rank-progress');
    if (existingProgress) existingProgress.remove();

    const needed = nextRank.min - current;
    const progress = ((current - (currentMax - (nextRank.min - currentMax))) / (nextRank.min - currentMax)) * 100;

    const progressDiv = document.createElement('div');
    progressDiv.className = 'rank-progress';

    progressDiv.innerHTML = `
        <div class="rank-progress-header">
            <span>Next: ${nextRank.name} ${nextRank.icon}</span>
            <span>${needed} vouches to go</span>
        </div>
        <div class="rank-progress-bar">
            <div class="rank-progress-fill" style="width: ${Math.min(progress, 100)}%;"></div>
        </div>
    `;

    const rankDisplay = document.querySelector('.rank-display');
    rankDisplay.after(progressDiv);
}

function calculateEarnedBadges(data) {
    const earned = [];
    const { vouches_received, vouches_given } = data;

    if (vouches_received >= 1) earned.push(BADGES.first_vouch);
    if (vouches_given >= 10) earned.push(BADGES.vouch_giver);
    if (vouches_received >= 25) earned.push(BADGES.vouch_collector);

    // Check if user joined in first week (simplified)
    const userAge = Date.now() - new Date(data.user.created_at).getTime();
    if (userAge < 7 * 24 * 60 * 60 * 1000) {
        earned.push(BADGES.early_adopter);
    }

    return earned;
}

function renderBadges(badges) {
    const profileHero = document.querySelector('.profile-hero');

    const existingBadges = document.querySelector('.badges-container');
    if (existingBadges) existingBadges.remove();

    const badgesDiv = document.createElement('div');
    badgesDiv.className = 'badges-container';
    badgesDiv.style.cssText = `
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 12px;
        margin: 24px 0;
    `;

    badges.forEach(badge => {
        const badgeEl = document.createElement('div');
        badgeEl.className = 'badge-item';
        badgeEl.title = badge.desc;
        badgeEl.style.cssText = `
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: var(--color-bg-card);
            border: 1px solid var(--color-border);
            border-radius: 8px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s;
        `;

        badgeEl.innerHTML = `
            <span style="font-size: 16px;">${badge.icon}</span>
            <span style="color: var(--color-text-secondary);">${badge.name}</span>
        `;

        badgeEl.addEventListener('mouseenter', () => {
            badgeEl.style.transform = 'translateY(-2px)';
            badgeEl.style.borderColor = 'var(--color-border-hover)';
        });

        badgeEl.addEventListener('mouseleave', () => {
            badgeEl.style.transform = 'translateY(0)';
            badgeEl.style.borderColor = 'var(--color-border)';
        });

        badgesDiv.appendChild(badgeEl);
    });

    const statsRow = profileHero.querySelector('.profile-stats-row');
    statsRow.after(badgesDiv);
}

function renderStreakDisplay(streak) {
    const profileHero = document.querySelector('.profile-hero');
    const statsRow = profileHero.querySelector('.profile-stats-row');

    // Create streak stat box (sleek minimal style)
    const streakBox = document.createElement('div');
    streakBox.className = 'stat-box';

    streakBox.innerHTML = `
        <div class="stat-value">🔥 ${streak}</div>
        <div class="stat-label">Day Streak</div>
    `;

    statsRow.appendChild(streakBox);
}

function renderConnectionSuggestions(suggestions) {
    // Create suggestions container after profile hero (sleek minimal style)
    const profileHero = document.querySelector('.profile-hero');

    const existingSuggestions = document.querySelector('.suggestions-container');
    if (existingSuggestions) existingSuggestions.remove();

    const suggestionsDiv = document.createElement('div');
    suggestionsDiv.className = 'suggestions-container section-card';

    let suggestionsHTML = `
        <h3>👥 People You May Know</h3>
        <p>Build your network by vouching for people you trust</p>
        <div>
    `;

    suggestions.forEach(user => {
        const username = user.username || user.first_name;
        const mutualCount = user.mutual_count || 0;
        const vouchCount = user.vouch_count || 0;

        suggestionsHTML += `
            <div class="suggestion-item">
                <div class="suggestion-info">
                    <div class="suggestion-username">@${username}</div>
                    <div class="suggestion-meta">
                        ${mutualCount > 0 ? `⭐ ${mutualCount} mutual connections` : `✅ ${vouchCount} vouches`}
                    </div>
                </div>
                <button class="btn-secondary" onclick="quickVouch(${user.telegram_user_id}, '${username}')">
                    Vouch
                </button>
            </div>
        `;
    });

    suggestionsHTML += `</div>`;
    suggestionsDiv.innerHTML = suggestionsHTML;

    profileHero.after(suggestionsDiv);
}

async function quickVouch(telegramUserId, username) {
    if (!state.currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/api/vouches`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_telegram_id: state.currentUser.user.telegram_user_id,
                to_username: username,
                group_chat_id: null,
                comment: null
            })
        });

        if (response.ok) {
            showToast(`✅ Vouched for @${username}!`, 'success');
            // Reload profile to update stats
            setTimeout(() => {
                loadUserProfile(state.currentUser.user.telegram_user_id);
            }, 1000);
        } else {
            const data = await response.json();
            showToast(data.detail || 'Failed to vouch', 'error');
        }
    } catch (error) {
        console.error('Error vouching:', error);
        showToast('Failed to vouch', 'error');
    }
}

// ==================== VOUCHES RECEIVED (SOCIAL PROOF GRID) ====================

function renderVouchesReceived(vouches) {
    const container = document.getElementById('vouchesReceivedList');
    container.innerHTML = '';

    if (!vouches || vouches.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                </div>
                <div class="empty-state-title">No vouches yet</div>
                <div class="empty-state-text">Share your profile to start collecting vouches!</div>
            </div>
        `;
        return;
    }

    // Render each vouch with profile picture and info
    vouches.forEach((vouch, index) => {
        const card = document.createElement('div');
        card.className = 'vouch-card';
        card.style.animationDelay = `${index * 50}ms`;

        const initials = getInitials(vouch.from_first_name || vouch.from_username);
        const timeAgo = getTimeAgo(vouch.created_at);

        card.innerHTML = `
            <div class="vouch-card-header">
                <div class="vouch-avatar">${initials}</div>
                <div class="vouch-user-info">
                    <div class="vouch-username">@${vouch.from_username || vouch.from_first_name}</div>
                    <div class="vouch-time">${timeAgo}</div>
                </div>
            </div>
            ${vouch.comment ? `<div class="vouch-comment">${escapeHtml(vouch.comment)}</div>` : ''}
        `;

        container.appendChild(card);
    });

    // Add stacking visualization effect
    if (vouches.length >= 3) {
        addStackingEffect(container);
    }
}

function addStackingEffect(container) {
    // Add a visual "stack preview" at the bottom showing total count
    const stackPreview = document.createElement('div');
    stackPreview.className = 'stack-preview';
    stackPreview.style.cssText = `
        margin-top: 16px;
        padding: 16px;
        background: linear-gradient(135deg, var(--color-accent-primary)11, var(--color-accent-secondary)11);
        border: 1px solid var(--color-accent-primary)33;
        border-radius: 12px;
        text-align: center;
        font-size: 14px;
        color: var(--color-text-secondary);
    `;

    const vouchCount = document.querySelectorAll('.vouch-card').length;
    stackPreview.innerHTML = `
        <div style="font-size: 24px; margin-bottom: 8px;">📚</div>
        <div style="font-weight: 600; color: var(--color-accent-primary);">
            ${vouchCount} people trust you
        </div>
        <div style="font-size: 12px; margin-top: 4px; color: var(--color-text-tertiary);">
            Keep building your reputation!
        </div>
    `;

    container.appendChild(stackPreview);
}

// ==================== VOUCHES GIVEN ====================

function renderVouchesGiven(vouches) {
    const container = document.getElementById('vouchesGivenList');
    container.innerHTML = '';

    if (!vouches || vouches.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <div class="empty-state-title">No vouches given</div>
                <div class="empty-state-text">Vouch for someone in your community group!</div>
            </div>
        `;
        return;
    }

    vouches.forEach((vouch, index) => {
        const card = document.createElement('div');
        card.className = 'vouch-card';
        card.style.animationDelay = `${index * 50}ms`;

        const initials = getInitials(vouch.to_first_name || vouch.to_username);
        const timeAgo = getTimeAgo(vouch.created_at);

        card.innerHTML = `
            <div class="vouch-card-header">
                <div class="vouch-avatar">${initials}</div>
                <div class="vouch-user-info">
                    <div class="vouch-username">@${vouch.to_username || vouch.to_first_name}</div>
                    <div class="vouch-time">${timeAgo}</div>
                </div>
            </div>
            ${vouch.comment ? `<div class="vouch-comment">${escapeHtml(vouch.comment)}</div>` : ''}
            <div class="vouch-actions">
                <button class="vouch-action-btn" data-vouch-id="${vouch.id}" data-action="edit">
                    Edit Comment
                </button>
                <button class="vouch-action-btn" data-vouch-id="${vouch.id}" data-action="undo">
                    Undo Vouch
                </button>
            </div>
        `;

        container.appendChild(card);
    });
}

// ==================== LEADERBOARD ====================

async function loadLeaderboard(type = 'most_vouched') {
    try {
        const response = await fetch(`${API_BASE}/api/leaderboards?type=${type}&limit=25`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to load leaderboard');
        }

        renderLeaderboard(data.leaderboard);

    } catch (error) {
        console.error('Error loading leaderboard:', error);
        showToast('Failed to load leaderboard', 'error');
    }
}

function renderLeaderboard(users) {
    const container = document.getElementById('leaderboardList');
    container.innerHTML = '';

    if (!users || users.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-title">No data yet</div>
                <div class="empty-state-text">Be the first on the leaderboard!</div>
            </div>
        `;
        return;
    }

    users.forEach((user, index) => {
        const item = document.createElement('div');
        item.className = 'leaderboard-item';
        item.style.animationDelay = `${index * 30}ms`;

        const initials = getInitials(user.first_name || user.username);
        const rank = index + 1;

        item.innerHTML = `
            <div class="leaderboard-rank">${rank}</div>
            <div class="leaderboard-avatar">${initials}</div>
            <div class="leaderboard-info">
                <div class="leaderboard-name">${user.first_name || 'User'}</div>
                <div class="leaderboard-username">@${user.username || 'username'}</div>
            </div>
            <div class="leaderboard-score">${user.vouch_count}</div>
        `;

        item.addEventListener('click', () => {
            // TODO: Navigate to user profile
            showToast('Profile view coming soon!', 'info');
        });

        container.appendChild(item);
    });
}

// ==================== TRUST NETWORK VISUALIZATION ====================

async function renderNetworkVisualization() {
    const container = document.getElementById('networkViz');

    if (!state.currentUser) return;

    // Prepare network data
    const nodes = [];
    const links = [];

    // Add current user as center node
    nodes.push({
        id: state.currentUser.user.telegram_user_id,
        name: state.currentUser.user.first_name || 'You',
        type: 'you'
    });

    // Add vouchers (people who vouched for you)
    state.currentUser.vouches_received_list.forEach(vouch => {
        nodes.push({
            id: `voucher_${vouch.from_username}`,
            name: vouch.from_username || vouch.from_first_name,
            type: 'voucher'
        });

        links.push({
            source: `voucher_${vouch.from_username}`,
            target: state.currentUser.user.telegram_user_id
        });
    });

    // Add vouched users (people you vouched for)
    state.currentUser.vouches_given_list.forEach(vouch => {
        nodes.push({
            id: `vouched_${vouch.to_username}`,
            name: vouch.to_username || vouch.to_first_name,
            type: 'vouched'
        });

        links.push({
            source: state.currentUser.user.telegram_user_id,
            target: `vouched_${vouch.to_username}`
        });
    });

    // D3.js force-directed graph
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Clear previous visualization
    container.innerHTML = '';

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    // Draw links
    const link = svg.append('g')
        .selectAll('line')
        .data(links)
        .enter()
        .append('line')
        .attr('stroke', 'rgba(99, 102, 241, 0.3)')
        .attr('stroke-width', 2);

    // Draw nodes
    const node = svg.append('g')
        .selectAll('circle')
        .data(nodes)
        .enter()
        .append('circle')
        .attr('r', d => d.type === 'you' ? 20 : 12)
        .attr('fill', d => {
            if (d.type === 'you') return '#4F46E5';
            if (d.type === 'voucher') return '#F59E0B';
            return '#10B981';
        })
        .attr('stroke', d => d.type === 'you' ? '#4F46E5' : 'none')
        .attr('stroke-width', d => d.type === 'you' ? 4 : 0)
        .style('cursor', 'pointer')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    // Add labels
    const label = svg.append('g')
        .selectAll('text')
        .data(nodes)
        .enter()
        .append('text')
        .text(d => d.name)
        .attr('font-size', d => d.type === 'you' ? 14 : 11)
        .attr('font-weight', d => d.type === 'you' ? 'bold' : 'normal')
        .attr('fill', '#B8C5D6')
        .attr('text-anchor', 'middle')
        .attr('dy', d => d.type === 'you' ? -30 : -20);

    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);

        label
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });

    function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
    }

    function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
    }

    function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
    }
}

// ==================== EVENT LISTENERS ====================

function setupEventListeners() {
    // Tab navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.currentTarget.dataset.tab;
            switchTab(tab);
        });
    });

    // Leaderboard type tabs
    document.querySelectorAll('.lb-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const type = e.currentTarget.dataset.board;

            // Update active state
            document.querySelectorAll('.lb-tab-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');

            // Load leaderboard
            state.leaderboardType = type;
            loadLeaderboard(type);
        });
    });

    // Search button
    document.getElementById('searchBtn').addEventListener('click', toggleSearch);

    // Share profile button
    document.getElementById('shareProfileBtn').addEventListener('click', shareProfile);

    // Center network button
    document.getElementById('centerNetworkBtn').addEventListener('click', () => {
        renderNetworkVisualization();
    });

    // Vouch action buttons (delegated)
    document.addEventListener('click', (e) => {
        if (e.target.matches('.vouch-action-btn')) {
            const vouchId = e.target.dataset.vouchId;
            const action = e.target.dataset.action;

            if (action === 'edit') {
                editVouchComment(vouchId);
            } else if (action === 'undo') {
                undoVouch(vouchId);
            }
        }
    });
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}Tab`).classList.add('active');

    state.currentTab = tabName;

    // Load tab-specific data
    if (tabName === 'leaderboard') {
        loadLeaderboard(state.leaderboardType);
    } else if (tabName === 'network') {
        renderNetworkVisualization();
    }
}

function toggleSearch() {
    const searchBar = document.getElementById('searchBar');
    const isVisible = searchBar.style.display !== 'none';

    searchBar.style.display = isVisible ? 'none' : 'block';

    if (!isVisible) {
        document.getElementById('searchInput').focus();
    }
}

async function shareProfile() {
    if (!state.currentUser) return;

    const userId = state.currentUser.user.telegram_user_id;
    const username = state.currentUser.user.username;
    const shareText = `Check out my Vouch Beacon profile! I have ${state.currentUser.vouches_received} vouches.\n\nhttps://t.me/${BOT_USERNAME}?start=profile_${userId}`;

    if (tg && tg.shareMessage) {
        tg.shareMessage(shareText);
    } else {
        // Fallback: copy to clipboard
        navigator.clipboard.writeText(shareText);
        showToast('Profile link copied to clipboard!', 'success');
    }
}

async function editVouchComment(vouchId) {
    const newComment = prompt('Enter new comment (max 120 characters):');
    if (!newComment) return;

    try {
        const response = await fetch(`${API_BASE}/api/vouches/${vouchId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_telegram_id: state.currentUser.user.telegram_user_id,
                comment: newComment
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update comment');
        }

        showToast('Comment updated!', 'success');
        await loadUserProfile(state.currentUser.user.telegram_user_id);

    } catch (error) {
        console.error('Error updating comment:', error);
        showToast('Failed to update comment', 'error');
    }
}

async function undoVouch(vouchId) {
    if (!confirm('Are you sure you want to undo this vouch?')) return;

    try {
        const response = await fetch(`${API_BASE}/api/vouches/${vouchId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_telegram_id: state.currentUser.user.telegram_user_id
            })
        });

        if (!response.ok) {
            throw new Error('Failed to undo vouch');
        }

        showToast('Vouch undone', 'success');
        await loadUserProfile(state.currentUser.user.telegram_user_id);

    } catch (error) {
        console.error('Error undoing vouch:', error);
        showToast('Failed to undo vouch', 'error');
    }
}

// ==================== UTILITY FUNCTIONS ====================

function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(' ');
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
}

function getTimeAgo(timestamp) {
    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diff = now - then;

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 7) return new Date(timestamp).toLocaleDateString();
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'just now';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function showError(message) {
    document.getElementById('loadingScreen').innerHTML = `
        <div style="text-align: center; padding: 32px;">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--color-error); margin-bottom: 16px;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <h2 style="font-size: 20px; margin-bottom: 8px;">Error</h2>
            <p style="color: var(--color-text-tertiary);">${message}</p>
        </div>
    `;
}

// ==================== START APP ====================

document.addEventListener('DOMContentLoaded', init);
