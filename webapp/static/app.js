// LocalVouch - Clean, Fast, Professional
// No bloat, no unnecessary features

// Global State
const state = {
    currentUser: null,
    currentTab: 'vouch',
    selectedUser: null,
    selectedThumbType: null,
};

// Telegram WebApp
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    const telegramUser = tg.initDataUnsafe?.user;

    if (!telegramUser) {
        showToast('Please open this app from Telegram', 'error');
        return;
    }

    // Initialize user
    try {
        showLoading();
        const response = await fetch('/api/profile/init', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                telegram_user_id: telegramUser.id,
                username: telegramUser.username,
                first_name: telegramUser.first_name,
                last_name: telegramUser.last_name
            })
        });

        const data = await response.json();
        state.currentUser = data.user;

        initUI();
        loadInitialData();
        hideLoading();
    } catch (error) {
        console.error('Init error:', error);
        showToast('Failed to initialize app', 'error');
        hideLoading();
    }
}

function initUI() {
    // Navigation
    const navBtns = document.querySelectorAll('.nav-btn');
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });

    // Search
    const searchInput = document.getElementById('searchInput');
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            handleSearch(e.target.value);
        }, 300);
    });

    // Modal close
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('profileModal').addEventListener('click', (e) => {
        if (e.target.id === 'profileModal') {
            closeModal();
        }
    });

    // Thumbs buttons
    document.getElementById('thumbUpBtn').addEventListener('click', () => selectThumb(true));
    document.getElementById('thumbDownBtn').addEventListener('click', () => selectThumb(false));

    // Submit vouch
    document.getElementById('submitVouchBtn').addEventListener('click', submitVouch);

    // Message character counter
    const vouchMessage = document.getElementById('vouchMessage');
    vouchMessage.addEventListener('input', () => {
        document.getElementById('charCount').textContent = vouchMessage.value.length;
    });

    // Share button
    document.getElementById('shareBtn').addEventListener('click', shareProfile);

    // Start on Vouch tab
    switchTab('vouch');
}

async function loadInitialData() {
    // Load data for current tab
    if (state.currentTab === 'vouch') {
        loadRecentUsers();
    } else if (state.currentTab === 'me') {
        loadMyProfile();
    } else if (state.currentTab === 'community') {
        loadCommunity();
    } else if (state.currentTab === 'groups') {
        loadGroups();
    }
}

function switchTab(tab) {
    state.currentTab = tab;

    // Update nav
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tab}-tab`).classList.add('active');

    // Load data
    loadInitialData();
}

// SEARCH
async function handleSearch(query) {
    if (!query || query.length < 2) {
        document.getElementById('searchResults').innerHTML = '';
        return;
    }

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        renderSearchResults(data.results || []);
    } catch (error) {
        console.error('Search error:', error);
    }
}

function renderSearchResults(users) {
    const container = document.getElementById('searchResults');

    if (users.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No users found</div></div>';
        return;
    }

    container.innerHTML = users.map(user => `
        <div class="user-card" onclick="openProfile(${user.telegram_user_id})">
            <div class="user-card-header">
                <div class="user-card-info">
                    <div class="user-card-name">${escapeHtml(user.first_name || 'User')}</div>
                    <div class="user-card-username">@${escapeHtml(user.username || 'unknown')}</div>
                </div>
                <div class="user-card-counts">
                    <span>👍 ${user.thumbs_up_count || 0}</span>
                    <span>👎 ${user.thumbs_down_count || 0}</span>
                </div>
            </div>
            <div class="rank-badge ${user.rank}">
                <span class="rank-emoji">${getRankEmoji(user.rank)}</span>
                <span class="rank-text">${getRankName(user.rank)}</span>
            </div>
        </div>
    `).join('');
}

// RECENT USERS
async function loadRecentUsers() {
    try {
        const response = await fetch('/api/users?limit=20');
        const data = await response.json();

        const container = document.getElementById('recentUsers');
        container.innerHTML = (data.users || []).map(user => `
            <div class="user-card" onclick="openProfile(${user.telegram_user_id})">
                <div class="user-card-header">
                    <div class="user-card-info">
                        <div class="user-card-name">${escapeHtml(user.first_name || 'User')}</div>
                        <div class="user-card-username">@${escapeHtml(user.username || 'unknown')}</div>
                    </div>
                    <div class="user-card-counts">
                        <span>👍 ${user.thumbs_up_count || 0}</span>
                        <span>👎 ${user.thumbs_down_count || 0}</span>
                    </div>
                </div>
                <div class="rank-badge ${user.rank}">
                    <span class="rank-emoji">${getRankEmoji(user.rank)}</span>
                    <span class="rank-text">${getRankName(user.rank)}</span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Load recent users error:', error);
    }
}

// MY PROFILE
async function loadMyProfile() {
    if (!state.currentUser) return;

    try {
        const response = await fetch(`/api/profile/${state.currentUser.telegram_user_id}`);
        const data = await response.json();
        const user = data.user;

        // Update UI
        document.getElementById('myName').textContent = user.first_name || 'User';
        document.getElementById('myUsername').textContent = `@${user.username || 'unknown'}`;
        document.getElementById('myThumbsUp').textContent = user.thumbs_up_count || 0;
        document.getElementById('myThumbsDown').textContent = user.thumbs_down_count || 0;

        // Rank badge
        const rankBadge = document.getElementById('myRank');
        rankBadge.className = `rank-badge ${user.rank}`;
        rankBadge.innerHTML = `
            <span class="rank-emoji">${getRankEmoji(user.rank)}</span>
            <span class="rank-text">${getRankName(user.rank)}</span>
        `;

        // Progress
        updateProgress(user);

        // Vouches
        loadMyVouches();
    } catch (error) {
        console.error('Load profile error:', error);
    }
}

function updateProgress(user) {
    const thumbsUp = user.thumbs_up_count || 0;
    const thumbsDown = user.thumbs_down_count || 0;

    let nextMilestone, progress, text;

    if (thumbsDown === 0) {
        if (thumbsUp < 3) {
            nextMilestone = 3;
            progress = (thumbsUp / 3) * 100;
            text = `Get ${3 - thumbsUp} more vouches to become TRUSTED`;
        } else if (thumbsUp < 10) {
            nextMilestone = 10;
            progress = (thumbsUp / 10) * 100;
            text = `Get ${10 - thumbsUp} more vouches to become TOP-RATED`;
        } else {
            progress = 100;
            text = '🎉 You\'re TOP-RATED!';
        }
    } else {
        // Has warnings
        document.getElementById('progressContainer').style.display = 'none';
        return;
    }

    document.getElementById('progressContainer').style.display = 'block';
    document.getElementById('progressText').textContent = text;
    document.getElementById('progressFill').style.width = `${progress}%`;
}

async function loadMyVouches() {
    try {
        const [received, given] = await Promise.all([
            fetch(`/api/profile/${state.currentUser.telegram_user_id}/vouches`).then(r => r.json()),
            fetch(`/api/profile/${state.currentUser.telegram_user_id}/vouches-given`).then(r => r.json())
        ]);

        renderVouches('receivedVouches', received.vouches || [], true);
        renderVouches('givenVouches', given.vouches || [], false);
    } catch (error) {
        console.error('Load vouches error:', error);
    }
}

function renderVouches(containerId, vouches, showVouchBack) {
    const container = document.getElementById(containerId);

    if (vouches.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No vouches yet</div></div>';
        return;
    }

    container.innerHTML = vouches.map(vouch => `
        <div class="vouch-item">
            <div class="vouch-header">
                <div class="vouch-user" onclick="openProfile(${vouch.from_user_id || vouch.to_user_id})">
                    <span class="vouch-type">${vouch.is_thumbs_up ? '👍' : '👎'}</span>
                    <div>
                        <div class="vouch-name">${escapeHtml(vouch.first_name || 'User')}</div>
                        <div class="vouch-username">@${escapeHtml(vouch.username || 'unknown')}</div>
                    </div>
                </div>
            </div>
            ${vouch.message ? `<div class="vouch-message">${escapeHtml(vouch.message)}</div>` : ''}
            <div class="vouch-time">${formatTime(vouch.created_at)}</div>
            ${showVouchBack && !hasVouchedFor(vouch.from_user_id) ?
                `<button class="vouch-back-btn" onclick="openProfile(${vouch.from_user_id})">Vouch Back</button>` : ''}
        </div>
    `).join('');
}

function hasVouchedFor(userId) {
    // TODO: Track this in state
    return false;
}

// COMMUNITY
async function loadCommunity() {
    try {
        const [leaderboard, activity] = await Promise.all([
            fetch('/api/leaderboards/most_vouched?limit=10').then(r => r.json()),
            fetch('/api/activity?limit=20').then(r => r.json())
        ]);

        renderTopTrusted(leaderboard.leaderboard || []);
        renderActivity(activity.activity || []);
    } catch (error) {
        console.error('Load community error:', error);
    }
}

function renderTopTrusted(users) {
    const container = document.getElementById('topTrusted');

    container.innerHTML = users.map(user => `
        <div class="user-card" onclick="openProfile(${user.telegram_user_id})">
            <div class="user-card-header">
                <div class="user-card-info">
                    <div class="user-card-name">${escapeHtml(user.first_name || 'User')}</div>
                    <div class="user-card-username">@${escapeHtml(user.username || 'unknown')}</div>
                </div>
                <div class="user-card-counts">
                    <span>👍 ${user.thumbs_up_count || 0}</span>
                </div>
            </div>
            <div class="rank-badge ${user.rank}">
                <span class="rank-emoji">${getRankEmoji(user.rank)}</span>
                <span class="rank-text">${getRankName(user.rank)}</span>
            </div>
        </div>
    `).join('');
}

function renderActivity(activities) {
    const container = document.getElementById('recentActivity');

    if (activities.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No recent activity</div></div>';
        return;
    }

    container.innerHTML = activities.slice(0, 20).map(activity => {
        if (activity.activity_type === 'vouch') {
            return `
                <div class="activity-item">
                    <div class="activity-text">
                        <strong>${escapeHtml(activity.from_first_name)}</strong> vouched for
                        <strong>${escapeHtml(activity.to_first_name)}</strong>
                        ${activity.is_thumbs_up ? '👍' : '👎'}
                    </div>
                    <div class="activity-time">${formatTime(activity.created_at)}</div>
                </div>
            `;
        } else if (activity.activity_type === 'rank_up') {
            return `
                <div class="activity-item">
                    <div class="activity-text">
                        <strong>${escapeHtml(activity.first_name)}</strong> reached
                        <strong>${getRankName(activity.new_rank)}</strong> ${getRankEmoji(activity.new_rank)}
                    </div>
                    <div class="activity-time">${formatTime(activity.created_at)}</div>
                </div>
            `;
        }
        return '';
    }).join('');
}

// GROUPS
async function loadGroups() {
    try {
        const response = await fetch('/api/community-groups');
        const data = await response.json();

        renderGroups(data.groups || []);
    } catch (error) {
        console.error('Load groups error:', error);
    }
}

function renderGroups(groups) {
    const container = document.getElementById('communityGroups');

    if (groups.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No groups yet</div></div>';
        return;
    }

    container.innerHTML = groups.map(group => `
        <div class="group-card">
            <div class="group-header">
                <div class="group-icon">${group.icon_emoji}</div>
                <div class="group-info">
                    <div class="group-name">${escapeHtml(group.name)}</div>
                    <div class="group-members">${group.member_count.toLocaleString()} members</div>
                </div>
            </div>
            ${group.description ? `<div class="group-description">${escapeHtml(group.description)}</div>` : ''}
            <button class="group-join-btn" onclick="joinGroup('${group.telegram_link}')">Join Group</button>
        </div>
    `).join('');
}

function joinGroup(link) {
    tg.openTelegramLink(link);
}

// PROFILE MODAL
async function openProfile(userId) {
    if (!userId || userId === state.currentUser.telegram_user_id) {
        showToast('This is you!');
        return;
    }

    try {
        showLoading();
        const response = await fetch(`/api/profile/${userId}`);
        const data = await response.json();
        const user = data.user;

        state.selectedUser = user;
        state.selectedThumbType = null;

        // Update modal
        document.getElementById('modalName').textContent = user.first_name || 'User';
        document.getElementById('modalUsername').textContent = `@${user.username || 'unknown'}`;
        document.getElementById('modalThumbsUp').textContent = user.thumbs_up_count || 0;
        document.getElementById('modalThumbsDown').textContent = user.thumbs_down_count || 0;

        const rankBadge = document.getElementById('modalRank');
        rankBadge.className = `rank-badge ${user.rank}`;
        rankBadge.innerHTML = `
            <span class="rank-emoji">${getRankEmoji(user.rank)}</span>
            <span class="rank-text">${getRankName(user.rank)}</span>
        `;

        // Reset thumbs selection
        document.getElementById('thumbUpBtn').classList.remove('selected');
        document.getElementById('thumbDownBtn').classList.remove('selected');
        document.getElementById('messageBox').style.display = 'none';
        document.getElementById('vouchMessage').value = '';
        document.getElementById('charCount').textContent = '0';

        // Load vouches
        const vouchesResponse = await fetch(`/api/profile/${userId}/vouches`);
        const vouchesData = await vouchesResponse.json();
        renderModalVouches(vouchesData.vouches || []);

        // Show modal
        document.getElementById('profileModal').classList.add('active');
        hideLoading();
    } catch (error) {
        console.error('Open profile error:', error);
        showToast('Failed to load profile', 'error');
        hideLoading();
    }
}

function closeModal() {
    document.getElementById('profileModal').classList.remove('active');
    state.selectedUser = null;
    state.selectedThumbType = null;
}

function selectThumb(isThumbsUp) {
    state.selectedThumbType = isThumbsUp;

    document.getElementById('thumbUpBtn').classList.toggle('selected', isThumbsUp);
    document.getElementById('thumbDownBtn').classList.toggle('selected', !isThumbsUp);

    document.getElementById('messageBox').style.display = 'block';
}

async function submitVouch() {
    if (!state.selectedUser || state.selectedThumbType === null) {
        showToast('Please select thumbs up or down', 'error');
        return;
    }

    const message = document.getElementById('vouchMessage').value.trim();

    try {
        showLoading();
        const response = await fetch('/api/vouch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_user_id: state.currentUser.telegram_user_id,
                to_username: state.selectedUser.username,
                message: message || null,
                is_thumbs_up: state.selectedThumbType
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`${state.selectedThumbType ? 'Vouched' : 'Warned'} for @${state.selectedUser.username}!`, 'success');

            // Haptic feedback
            if (tg.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred('success');
            }

            closeModal();

            // Reload data
            if (state.currentTab === 'me') {
                loadMyProfile();
            }
        } else {
            showToast(data.error || 'Failed to submit vouch', 'error');
        }

        hideLoading();
    } catch (error) {
        console.error('Submit vouch error:', error);
        showToast('Failed to submit vouch', 'error');
        hideLoading();
    }
}

function renderModalVouches(vouches) {
    const container = document.getElementById('modalVouchesList');
    document.getElementById('vouchesCount').textContent = vouches.length;

    if (vouches.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">No vouches yet</div></div>';
        return;
    }

    container.innerHTML = vouches.map(vouch => `
        <div class="vouch-item">
            <div class="vouch-header">
                <div class="vouch-user" onclick="closeModal(); openProfile(${vouch.from_user_id})">
                    <span class="vouch-type">${vouch.is_thumbs_up ? '👍' : '👎'}</span>
                    <div>
                        <div class="vouch-name">${escapeHtml(vouch.first_name || 'User')}</div>
                        <div class="vouch-username">@${escapeHtml(vouch.username || 'unknown')}</div>
                    </div>
                </div>
            </div>
            ${vouch.message ? `<div class="vouch-message">"${escapeHtml(vouch.message)}"</div>` : ''}
            <div class="vouch-time">${formatTime(vouch.created_at)}</div>
        </div>
    `).join('');
}

// SHARE
function shareProfile() {
    const shareUrl = `https://t.me/${tg.initDataUnsafe?.bot_info?.username || 'VouchPortalBot'}?startapp=ref_${state.currentUser.telegram_user_id}`;
    const shareText = `Check out my LocalVouch profile! ${shareUrl}`;

    tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`);
}

// UTILITIES
function getRankEmoji(rank) {
    const emojis = {
        'new': '🆕',
        'building': '⏳',
        'trusted': '✅',
        'top_rated': '⭐',
        'mixed': '⚠️',
        'caution': '🚫'
    };
    return emojis[rank] || '❓';
}

function getRankName(rank) {
    const names = {
        'new': 'NEW',
        'building': 'BUILDING',
        'trusted': 'TRUSTED',
        'top_rated': 'TOP-RATED',
        'mixed': 'MIXED REVIEWS',
        'caution': 'CAUTION'
    };
    return names[rank] || 'UNKNOWN';
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function showLoading() {
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}
