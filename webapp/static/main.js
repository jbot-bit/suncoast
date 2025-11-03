// Vouch Portal - Client-side JavaScript
// Handles all UI interactions, API calls, and Telegram WebApp integration

// Initialize Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Global state
let currentUser = null;
let currentTab = 'profile';
let allUsers = [];
let currentFilter = 'all';
let currentCommunityView = 'activity';
let currentLeaderboardType = 'most_vouched';
let botUsername = 'VouchPortalBot'; // Default, will be fetched from API

// API Base URL
const API_BASE = window.location.origin;

// ========================================
// API: Retry Helper with Exponential Backoff
// ========================================
async function fetchWithRetry(url, options = {}, maxRetries = 3) {
    let lastError;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(url, options);

            // Success - return response
            if (response.ok) {
                return response;
            }

            // Don't retry on client errors (4xx) - these won't fix themselves
            if (response.status >= 400 && response.status < 500) {
                return response; // Return to let caller handle the error
            }

            // Server errors (5xx) - retry with backoff
            if (attempt < maxRetries - 1) {
                const delay = Math.pow(2, attempt) * 1000; // Exponential: 1s, 2s, 4s
                console.log(`Server error (${response.status}), retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }

            return response; // Return last response to let caller handle

        } catch (error) {
            lastError = error;

            // Network errors - retry with backoff
            if (attempt < maxRetries - 1) {
                const delay = Math.pow(2, attempt) * 1000;
                console.log(`Network error, retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
        }
    }

    // All retries failed
    throw lastError || new Error('All retry attempts failed');
}

function getErrorMessage(error, response = null) {
    // Check for offline/network issues
    if (!navigator.onLine) {
        return 'You appear to be offline. Please check your internet connection.';
    }

    if (error.name === 'TypeError' && error.message.includes('fetch')) {
        return 'Network connection failed. Please check your internet and try again.';
    }

    // HTTP status errors
    if (response) {
        if (response.status === 404) {
            return 'Data not found. Please try refreshing.';
        } else if (response.status === 500) {
            return 'Server error. Please try again in a moment.';
        } else if (response.status === 503) {
            return 'Service temporarily unavailable. Please try again.';
        }
    }

    // Generic error with message
    return error.message || 'Something went wrong. Please try again.';
}

// ========================================
// SECURITY: HTML Escaping Functions
// ========================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sanitizeMessage(message) {
    if (!message) return '';
    return escapeHtml(message.trim());
}

// ========================================
// Skeleton Loading States
// ========================================
const SkeletonScreens = {
    profile: () => `
        <div class="profile-card">
            <div class="skeleton-pulse" style="height: 200px; border-radius: 12px;"></div>
        </div>
    `,
    vouchList: () => `
        <div class="skeleton-pulse" style="height: 80px; border-radius: 8px; margin-bottom: 12px;"></div>
    `,
    activityFeed: () => `
        <div class="skeleton-pulse" style="height: 60px; border-radius: 8px; margin-bottom: 8px;"></div>
    `,
    communityGrid: () => `
        <div class="skeleton-pulse" style="height: 120px; border-radius: 12px;"></div>
    `,
    leaderboard: () => `
        <div class="skeleton-pulse" style="height: 70px; border-radius: 8px; margin-bottom: 8px;"></div>
    `
};

const SkeletonHelper = {
    show: (containerId, type, count = 3) => {
        const container = document.getElementById(containerId);
        if (!container) return;

        const skeletonFunc = SkeletonScreens[type];
        if (!skeletonFunc) return;

        let html = '';
        for (let i = 0; i < count; i++) {
            html += skeletonFunc();
        }
        container.innerHTML = html;
    }
};

// ========================================
// Telegram TOS Compliance - Content Filter
// ========================================
const BANNED_WORDS = [
    // Scam/Fraud related
    'scam', 'fraud', 'fake', 'cheat', 'steal', 'hack', 'stolen',
    'phishing', 'ponzi', 'pyramid', 'mlm', 'money laundering',
    // Violence/Threats
    'kill', 'murder', 'attack', 'bomb', 'terrorism', 'terrorist',
    'violence', 'hurt', 'harm', 'weapon', 'gun', 'explosive',
    // Illegal activities
    'drug', 'cocaine', 'heroin', 'meth', 'illegal', 'smuggle',
    'counterfeit', 'piracy', 'pirated', 'cracked',
    // Hate speech
    'nazi', 'fascist', 'genocide', 'supremacy', 'racist',
    // Adult content
    'porn', 'xxx', 'nsfw', 'sexual', 'nude',
    // Gambling
    'casino', 'poker', 'bet', 'gambling', 'lottery',
    // Personal info
    'credit card', 'social security', 'ssn', 'password',
    'bank account', 'routing number',
    // Spam
    'buy now', 'click here', 'limited offer', 'act now',
    'free money', 'get rich', 'make money fast'
];

const SUSPICIOUS_PATTERNS = [
    // URLs with suspicious TLDs
    /(?:http[s]?:\/\/)?(?:www\.)?[a-zA-Z0-9-]+\.(?:xyz|tk|ml|ga|cf|gq)\b/gi,
    // Multiple special characters
    /[!@#$%^&*()]{4,}/g,
    // Excessive capitalization
    /\b[A-Z]{10,}\b/g,
    // Phone numbers
    /\+?\d{10,15}/g,
    // Email addresses
    /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
    // Crypto addresses
    /\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-Z0-9]{39,59})\b/g
];

function checkMessageCompliance(message) {
    if (!message) return { valid: true, warnings: [] };

    const warnings = [];
    let testMessage = message.toLowerCase();

    // Check for banned words
    for (const word of BANNED_WORDS) {
        const regex = new RegExp(`\\b${word}\\b`, 'i');
        if (regex.test(testMessage)) {
            warnings.push(`Contains prohibited term: "${word}"`);
        }
    }

    // Check for suspicious patterns
    for (const pattern of SUSPICIOUS_PATTERNS) {
        if (pattern.test(message)) {
            warnings.push('Contains suspicious content (URLs, contact info, or spam patterns)');
            break; // Only show this warning once
        }
    }

    return {
        valid: warnings.length === 0,
        warnings: warnings
    };
}

// ========================================
// MOBILE: Haptic Feedback Helper
// ========================================
function triggerHaptic(type = 'light') {
    if (!tg.HapticFeedback) return;

    const hapticMap = {
        light: 'impact',
        medium: 'impact',
        heavy: 'impact',
        success: 'notification',
        warning: 'notification',
        error: 'notification',
        selection: 'selection_change'
    };

    const style = hapticMap[type] || 'impact';

    if (style === 'impact') {
        tg.HapticFeedback.impactOccurred(type);
    } else if (style === 'notification') {
        tg.HapticFeedback.notificationOccurred(type);
    } else if (style === 'selection_change') {
        tg.HapticFeedback.selectionChanged();
    }
}

// Initialize app on load
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

async function initializeApp() {
    try {
        showLoading(true);

        // Debug: Log all Telegram data
        console.log('Telegram WebApp object:', tg);
        console.log('initDataUnsafe:', tg.initDataUnsafe);
        console.log('initData:', tg.initData);
        
        // Get user from Telegram WebApp
        let telegramUser = tg.initDataUnsafe?.user;
        console.log('Telegram user:', telegramUser);

        // DEVELOPMENT MODE: Use a test user if no Telegram data
        const isDevelopment = window.location.hostname === 'localhost' || 
                            window.location.hostname.includes('.replit.app');
        
        if (!telegramUser && isDevelopment) {
            console.warn('No Telegram user detected. Using test user for development.');
            // Use a test user for development
            telegramUser = {
                id: 999888777,  // Test user ID
                username: 'testuser',
                first_name: 'Test',
                last_name: 'User'
            };
        }

        if (!telegramUser) {
            showLoading(false);
            // Show instructions for proper setup
            const debugInfo = `
                <div style="padding: 40px; text-align: center;">
                    <h2>⚠️ Telegram Configuration Required</h2>
                    <p style="margin: 20px 0;">This app must be opened through your Telegram bot's Web App button.</p>
                    
                    <div style="margin: 30px auto; padding: 20px; background: rgba(255,255,255,0.1); border-radius: 8px; text-align: left; max-width: 500px;">
                        <h3 style="margin-bottom: 15px;">📱 How to set up:</h3>
                        <ol style="text-align: left; padding-left: 20px;">
                            <li>Open @BotFather in Telegram</li>
                            <li>Send /mybots</li>
                            <li>Select your bot</li>
                            <li>Click "Bot Settings" → "Menu Button"</li>
                            <li>Set URL: <code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 3px;">${window.location.origin}</code></li>
                            <li>Set Button Text: "Open Vouch Portal"</li>
                        </ol>
                    </div>
                    
                    <p style="margin-top: 20px;">After setup, open your bot and click the menu button to access the app.</p>
                    
                    <div style="margin-top: 20px; padding: 15px; background: rgba(255,0,0,0.1); border-radius: 8px; font-size: 12px;">
                        <p><strong>Debug Info:</strong></p>
                        <p>Current URL: ${window.location.href}</p>
                        <p>Platform: ${tg.platform || 'unknown'}</p>
                        <p>initData: ${tg.initData ? 'present but invalid' : 'empty'}</p>
                    </div>
                </div>
            `;
            document.getElementById('app').innerHTML = debugInfo;
            return;
        }

        // Initialize user (creates profile if doesn't exist)
        const initResponse = await fetch(`${API_BASE}/api/profile/init`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                telegram_user_id: telegramUser.id,
                username: telegramUser.username || null,
                first_name: telegramUser.first_name || null,
                last_name: telegramUser.last_name || null
            })
        });

        if (!initResponse.ok) {
            throw new Error(`Failed to initialize profile: ${initResponse.status}`);
        }

        // Fetch bot info and user profile in parallel
        const [botInfoResponse, profileResponse] = await Promise.all([
            fetch(`${API_BASE}/api/bot-info`),
            fetch(`${API_BASE}/api/profile/${telegramUser.id}`)
        ]);

        if (botInfoResponse.ok) {
            const botInfo = await botInfoResponse.json();
            botUsername = botInfo.bot_username || 'VouchPortalBot';
        }

        if (!profileResponse.ok) {
            const errorText = await profileResponse.text();
            console.error(`Profile loading failed - Status: ${profileResponse.status}, Response: ${errorText}`);
            throw new Error(`Failed to load profile: ${profileResponse.status} - ${errorText}`);
        }
        
        const data = await profileResponse.json();
        currentUser = data.user;

        // Fetch profile photo for current user
        fetchAndCacheProfilePhoto(currentUser.telegram_user_id);

        // Check if user is admin (get from environment or set dynamically)
        const adminElements = document.querySelectorAll('.admin-only');
        if (adminElements.length > 0) {
            // You can implement admin check here if needed
            // For now, hide admin sections by default
            adminElements.forEach(el => el.style.display = 'none');
        }

        // Setup UI
        setupEventListeners();
        updateHeaderBadge();
        loadProfileTab();

        showLoading(false);
    } catch (error) {
        console.error('Initialization error:', error);
        showLoading(false);
        document.getElementById('app').innerHTML = `
            <div style="padding: 40px; text-align: center;">
                <h2>❌ Error Loading App</h2>
                <p>${error.message}</p>
                <p>Please try again or contact support.</p>
            </div>
        `;
    }
}

// Event Listeners
function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            switchTab(e.target.dataset.tab);
        });
    });

    // Vouch form
    const vouchForm = document.getElementById('vouchForm');
    if (vouchForm) {
        vouchForm.addEventListener('submit', handleVouchSubmit);
    }

    // Character counter and compliance check
    const vouchMessage = document.getElementById('vouchMessage');
    if (vouchMessage) {
        vouchMessage.addEventListener('input', (e) => {
            updateCharCount();
            checkVouchMessageCompliance(e.target.value);
        });
    }
    
    // Vote buttons
    document.querySelectorAll('.vote-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            triggerHaptic('selection');
            document.querySelectorAll('.vote-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            document.getElementById('voteType').value = e.target.dataset.vote;
        });
    });

    // Profile buttons
    const requestVouchBtn = document.getElementById('requestVouchBtn');
    if (requestVouchBtn) {
        requestVouchBtn.addEventListener('click', handleRequestVouch);
    }

    const shareProfileBtn = document.getElementById('shareProfileBtn');
    if (shareProfileBtn) {
        shareProfileBtn.addEventListener('click', handleShareProfile);
    }

    // Community search
    const communitySearch = document.getElementById('communitySearch');
    if (communitySearch) {
        communitySearch.addEventListener('input', handleSearch);
    }

    // Global search in header
    const globalSearch = document.getElementById('globalSearch');
    if (globalSearch) {
        globalSearch.addEventListener('input', handleGlobalSearch);
        globalSearch.addEventListener('focus', () => {
            if (globalSearch.value.trim().length >= 2) {
                handleGlobalSearch({ target: globalSearch });
            }
        });
    }

    // Close search dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const searchDropdown = document.getElementById('searchResultsDropdown');
        const globalSearchInput = document.getElementById('globalSearch');
        if (searchDropdown && globalSearchInput &&
            !searchDropdown.contains(e.target) &&
            e.target !== globalSearchInput) {
            searchDropdown.classList.remove('show');
        }
    });

    // Community filters
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            triggerHaptic('light');
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.dataset.filter;
            filterCommunity();
        });
    });
    
    // Community view tabs
    document.querySelectorAll('.view-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const viewType = e.target.dataset.view;
            currentCommunityView = viewType;
            
            // Update tab buttons
            document.querySelectorAll('.view-tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Switch views
            document.querySelectorAll('.community-view').forEach(view => {
                view.style.display = 'none';
                view.classList.remove('active');
            });
            
            if (viewType === 'activity') {
                document.getElementById('activityView').style.display = 'block';
                document.getElementById('activityView').classList.add('active');
                loadActivityFeed();
            } else if (viewType === 'users') {
                document.getElementById('usersView').style.display = 'block';
                document.getElementById('usersView').classList.add('active');
                loadUsersView();
            } else if (viewType === 'groups') {
                document.getElementById('groupsView').style.display = 'block';
                document.getElementById('groupsView').classList.add('active');
                loadGroupsView();
            } else if (viewType === 'leaderboards') {
                document.getElementById('leaderboardsView').style.display = 'block';
                document.getElementById('leaderboardsView').classList.add('active');
                loadLeaderboardsView();
            }
        });
    });
    
    // Leaderboard tabs
    document.querySelectorAll('.lb-tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const boardType = e.target.dataset.board;
            currentLeaderboardType = boardType;
            
            // Update tab buttons
            document.querySelectorAll('.lb-tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Load leaderboard
            loadLeaderboard(boardType);
        });
    });
    
    // View toggle buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            const view = e.target.dataset.view;
            const grid = document.getElementById('communityGrid');
            if (view === 'list') {
                grid.classList.add('list-view');
            } else {
                grid.classList.remove('list-view');
            }
        });
    });

    // Modal close
    const closeModal = document.querySelector('.close');
    if (closeModal) {
        closeModal.addEventListener('click', () => {
            document.getElementById('profileModal').classList.remove('active');
        });
    }
    
    // Edit Profile button
    const editProfileBtn = document.getElementById('editProfileBtn');
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', openEditProfileModal);
    }
    
    // Edit Profile Modal close
    const closeEditModal = document.getElementById('closeEditModal');
    if (closeEditModal) {
        closeEditModal.addEventListener('click', () => {
            document.getElementById('editProfileModal').classList.remove('active');
        });
    }
    
    // Edit Profile form
    const editProfileForm = document.getElementById('editProfileForm');
    if (editProfileForm) {
        editProfileForm.addEventListener('submit', handleProfileUpdate);
    }
    
    // Bio character counter
    const editBio = document.getElementById('editBio');
    if (editBio) {
        editBio.addEventListener('input', () => {
            document.getElementById('bioCharCount').textContent = editBio.value.length;
        });
    }
    
    // Share Modal close
    const closeShareModal = document.getElementById('closeShareModal');
    if (closeShareModal) {
        closeShareModal.addEventListener('click', () => {
            document.getElementById('shareModal').classList.remove('active');
        });
    }
    
    // Copy link button
    const copyLinkBtn = document.getElementById('copyLinkBtn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', copyShareLink);
    }
    
    // Telegram share button
    const telegramShareBtn = document.getElementById('telegramShareBtn');
    if (telegramShareBtn) {
        telegramShareBtn.addEventListener('click', shareOnTelegram);
    }
    
    // Edit Vouch Modal close
    const closeEditVouchModal = document.getElementById('closeEditVouchModal');
    if (closeEditVouchModal) {
        closeEditVouchModal.addEventListener('click', () => {
            document.getElementById('editVouchModal').classList.remove('active');
        });
    }
    
    // Edit Vouch form
    const editVouchForm = document.getElementById('editVouchForm');
    if (editVouchForm) {
        editVouchForm.addEventListener('submit', handleEditVouchSubmit);
    }
    
    // Edit vouch message character counter
    const editVouchMessage = document.getElementById('editVouchMessage');
    if (editVouchMessage) {
        editVouchMessage.addEventListener('input', () => {
            document.getElementById('editVouchCharCount').textContent = editVouchMessage.value.length;
        });
    }
    
    // Return vouch button in mutual vouch toast
    const returnVouchBtn = document.getElementById('returnVouchBtn');
    if (returnVouchBtn) {
        returnVouchBtn.addEventListener('click', handleReturnVouch);
    }

    // Delegated event listener for edit and delete buttons (to avoid inline onclick)
    document.addEventListener('click', (e) => {
        // Delete vouch button
        if (e.target.classList.contains('btn-delete') || e.target.closest('.btn-delete')) {
            const btn = e.target.classList.contains('btn-delete') ? e.target : e.target.closest('.btn-delete');
            const vouchId = btn.dataset.vouchId;
            const vouchTo = btn.dataset.vouchTo;

            if (vouchId) {
                triggerHaptic('medium');
                handleDeleteVouch(parseInt(vouchId), vouchTo);
            }
            return;
        }

        // Edit vouch button
        if (e.target.classList.contains('btn-edit') || e.target.closest('.btn-edit')) {
            const btn = e.target.classList.contains('btn-edit') ? e.target : e.target.closest('.btn-edit');
            const vouchId = btn.dataset.vouchId;
            const vouchMessage = btn.dataset.vouchMessage;

            if (vouchId) {
                triggerHaptic('light');
                openEditVouchModal(parseInt(vouchId), vouchMessage);
            }
            return;
        }

        // Community card clicks
        const communityCard = e.target.closest('.community-card');
        if (communityCard && communityCard.dataset.userId) {
            triggerHaptic('light');
            loadUserProfile(parseInt(communityCard.dataset.userId));
            return;
        }

        // Leaderboard item clicks
        const leaderboardItem = e.target.closest('.leaderboard-item');
        if (leaderboardItem && leaderboardItem.dataset.userId) {
            triggerHaptic('light');
            loadUserProfile(parseInt(leaderboardItem.dataset.userId));
            return;
        }

        // Modal vouch button
        if (e.target.id === 'modalVouchBtn' || e.target.closest('#modalVouchBtn')) {
            const btn = e.target.id === 'modalVouchBtn' ? e.target : e.target.closest('#modalVouchBtn');
            const username = btn.dataset.username;
            if (username) {
                vouchUser(username);
            }
            return;
        }
    });

    // Check URL parameters for deep linking
    const urlParams = new URLSearchParams(window.location.search);
    const view = urlParams.get('view');
    const id = urlParams.get('id');

    if (view) {
        switchTab(view);
    }

    if (id && view === 'profile') {
        loadUserProfile(parseInt(id));
    }
}

// Tab Switching
function switchTab(tabName) {
    currentTab = tabName;

    // Haptic feedback on tab switch
    triggerHaptic('selection');

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    const targetTab = document.getElementById(`${tabName}-tab`);
    if (targetTab) {
        targetTab.classList.add('active');
    }

    // Load tab data
    switch (tabName) {
        case 'profile':
            loadProfileTab();
            break;
        case 'vouch':
            loadVouchTab();
            break;
        case 'community':
            loadCommunityTab();
            break;
        case 'insights':
            loadInsightsTab();
            break;
    }
}

// Helper function to set up profile event handlers
function setupProfileEventHandlers() {
    const requestVouchBtn = document.getElementById('requestVouchBtn');
    if (requestVouchBtn) {
        requestVouchBtn.addEventListener('click', handleRequestVouch);
    }

    const shareProfileBtn = document.getElementById('shareProfileBtn');
    if (shareProfileBtn) {
        shareProfileBtn.addEventListener('click', handleShareProfile);
    }

    const editProfileBtn = document.getElementById('editProfileBtn');
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', openEditProfileModal);
    }

    // Vouch breakdown toggle
    const vouchBreakdownToggle = document.getElementById('vouchBreakdownToggle');
    if (vouchBreakdownToggle) {
        vouchBreakdownToggle.addEventListener('click', () => {
            const content = document.getElementById('vouchBreakdownContent');
            const icon = vouchBreakdownToggle.querySelector('.toggle-icon');
            if (content && icon) {
                const isOpen = content.style.display !== 'none';
                content.style.display = isOpen ? 'none' : 'block';
                icon.textContent = isOpen ? '▼' : '▲';
            }
        });
    }
}

// Helper function to create profile card HTML
function createProfileCardHTML(user, data) {
    const rankEmoji = getRankEmoji(data.user.rank);
    const rankName = getRankName(data.user.rank);
    const username = user.username || user.first_name;
    const positiveVotes = data.user.positive_votes || 0;
    const negativeVotes = data.user.negative_votes || 0;
    const ratingPercentage = data.user.rating_percentage || 100;
    const streakDays = data.user.streak_days || 0;

    // NEW: Simplified rank + level system
    const activityPoints = data.user.activity_points || 0;
    const currentLevel = data.user.current_level || 1;
    const levelDisplay = data.user.level_display || 'Lvl 1 ★';
    const progressData = data.user.level_progress || {};
    const pointsToNext = progressData.points_needed || 0;
    const levelProgress = progressData.progress_percent || 0;

    const bioSection = data.user.bio ? `
        <div class="profile-bio" id="profileBio">
            <p id="bioText">${escapeHtml(data.user.bio)}</p>
        </div>
    ` : '<div class="profile-bio" id="profileBio" style="display: none;"><p id="bioText"></p></div>';

    const locationSection = data.user.location ? `
        <div class="profile-location" id="profileLocation">
            <span class="location-icon"></span>
            <span id="locationText">${escapeHtml(data.user.location)}</span>
        </div>
    ` : '<div class="profile-location" id="profileLocation" style="display: none;"><span class="location-icon"></span><span id="locationText"></span></div>';

    let ratingClass = 'rating-display';
    if (ratingPercentage >= 80) {
        ratingClass += ' rating-high';
    } else if (ratingPercentage >= 60) {
        ratingClass += ' rating-medium';
    } else {
        ratingClass += ' rating-low';
    }

    const streakClass = streakDays > 0 ? 'active-streak' : '';
    const streakText = streakDays > 0 ? `🔥 ${streakDays}` : '0';
    const totalVouches = positiveVotes + negativeVotes;

    // Profile photo
    const profilePhotoHTML = data.user.profile_picture_url 
        ? `<div class="avatar" id="profileAvatar" style="background-image: url(${API_BASE}/api/photo-proxy/${data.user.profile_picture_url}); background-size: cover; background-position: center;"></div>`
        : `<div class="avatar" id="profileAvatar">👤</div>`;

    // Telegram profile link
    const telegramUsername = user.username || null;
    const telegramLink = telegramUsername ? `https://t.me/${telegramUsername}` : `tg://user?id=${user.telegram_user_id}`;

    return `
        <div class="profile-card">
            <div class="profile-header">
                <a href="${telegramLink}" target="_blank" class="avatar-link" title="Open in Telegram">
                    ${profilePhotoHTML}
                </a>
                <div class="profile-info">
                    <a href="${telegramLink}" target="_blank" class="profile-name-link" title="Open in Telegram">
                        <h2 id="profileName">@${escapeHtml(username)}</h2>
                    </a>
                    <div class="rank-badge-large ${data.user.rank}" id="profileRank">${rankEmoji} ${rankName}</div>
                </div>
                <button class="btn-icon" id="editProfileBtn" title="Edit Profile" aria-label="Edit Profile">✏️</button>
            </div>

            ${bioSection}
            ${locationSection}

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="totalVouchCount">${totalVouches}</div>
                    <div class="stat-label">Total Vouches</div>
                </div>
                <div class="stat-card streak-card ${streakClass}">
                    <div class="stat-value" id="streakCount">${streakText}</div>
                    <div class="stat-label">Day Streak</div>
                </div>
            </div>

            <!-- Vouch Breakdown Dropdown -->
            <div class="vouch-breakdown-section">
                <button class="vouch-breakdown-toggle" id="vouchBreakdownToggle">
                    <span>📊 Vouch Breakdown</span>
                    <span class="toggle-icon">▼</span>
                </button>
                <div class="vouch-breakdown-content" id="vouchBreakdownContent" style="display: none;">
                    <div class="breakdown-stats">
                        <div class="breakdown-item positive">
                            <span class="breakdown-icon">👍</span>
                            <span class="breakdown-label">Positive</span>
                            <span class="breakdown-value" id="positiveVotes">${positiveVotes}</span>
                        </div>
                        <div class="breakdown-item negative">
                            <span class="breakdown-icon">👎</span>
                            <span class="breakdown-label">Negative</span>
                            <span class="breakdown-value" id="negativeVotes">${negativeVotes}</span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="progress-section">
                <div class="progress-header">
                    <span>Progress to Next Rank</span>
                    <span id="progressText">0/0</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                </div>
            </div>

            <div class="action-buttons">
                <button class="btn btn-primary" id="requestVouchBtn">
                    💬 Request Vouch
                </button>
                <button class="btn btn-secondary" id="shareProfileBtn">
                    📤 Share Profile
                </button>
            </div>
        </div>
    `;
}

// Profile Tab
async function loadProfileTab() {
    if (!currentUser) return;

    try {
        // Show skeleton while loading
        const profileCard = document.querySelector('.profile-card');
        if (profileCard) {
            profileCard.outerHTML = SkeletonScreens.profile();
        }
        SkeletonHelper.show('receivedVouches', 'vouchList', 2);
        SkeletonHelper.show('givenVouches', 'vouchList', 2);

        // Use retry logic for fetching profile
        const response = await fetchWithRetry(`${API_BASE}/api/profile/${currentUser.telegram_user_id}`);

        if (!response.ok) {
            const errorMsg = getErrorMessage(new Error(`HTTP ${response.status}`), response);
            throw new Error(errorMsg);
        }

        const data = await response.json();

        // Replace skeleton with actual profile card
        const skeletonCard = document.querySelector('.profile-card');
        if (skeletonCard) {
            skeletonCard.outerHTML = createProfileCardHTML(currentUser, data);
        }

        // Update progress bar (this needs to be called after the card is created)
        updateProgressBar(data.user.total_vouches, data.next_rank_threshold, data.progress_percentage);

        // Render vouches
        renderVouches('receivedVouches', data.vouches_received);
        renderVouches('givenVouches', data.vouches_given, true); // true = show edit button

        // Reattach event handlers for buttons in the profile card
        setupProfileEventHandlers();
    } catch (error) {
        console.error('Error loading profile:', error);

        // User-friendly error message with retry option
        const errorMsg = getErrorMessage(error);
        showToast(errorMsg, 'error');

        // Show retry UI in the profile card
        const profileCard = document.querySelector('.profile-card');
        if (profileCard) {
            profileCard.innerHTML = `
                <div style="padding: 40px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
                    <h3 style="margin-bottom: 12px;">Failed to Load Profile</h3>
                    <p style="color: var(--text-secondary); margin-bottom: 24px;">${errorMsg}</p>
                    <button class="btn btn-primary" onclick="loadProfileTab()">
                        🔄 Retry
                    </button>
                </div>
            `;
        }
    }
}

function updateProgressBar(current, next, percentage) {
    // Handle max rank achieved (strictly null or undefined, not 0)
    if (next == null) {
        document.getElementById('progressText').textContent = '👑 Max rank achieved!';
        document.getElementById('progressFill').style.width = '100%';
        
        // Remove pulse effect for max rank users
        const requestBtn = document.getElementById('requestVouchBtn');
        if (requestBtn) {
            requestBtn.classList.remove('pulse');
        }
        return;
    }
    
    const remaining = next - current;
    let progressText = `${current}/${next}`;
    
    // Add progress pressure message if close to next rank
    if (remaining > 0 && remaining <= 3) {
        progressText = `Only ${remaining} to reach next rank!`;
    }
    
    document.getElementById('progressText').textContent = progressText;
    document.getElementById('progressFill').style.width = `${percentage}%`;
    
    // Add/remove pulse effect on Request Vouch button based on verification status
    const requestBtn = document.getElementById('requestVouchBtn');
    if (requestBtn && current < 3) {
        requestBtn.classList.add('pulse');
    } else if (requestBtn) {
        requestBtn.classList.remove('pulse');
    }
}

function renderVouches(containerId, vouches, showEditButton = false) {
    const container = document.getElementById(containerId);

    if (!vouches || vouches.length === 0) {
        container.innerHTML = '<div class="empty-state">No vouches yet</div>';
        return;
    }

    container.innerHTML = vouches.map(vouch => {
        const isPending = vouch.is_pending || !vouch.username;
        const displayName = isPending ? `@${vouch.to_username}` : `@${vouch.username || vouch.first_name}`;
        const statusBadge = isPending ? '<span style="color: #888; font-size: 11px;">⏳ Pending</span>' : '';
        const canEdit = showEditButton && currentUser && vouch.from_user_id === currentUser.telegram_user_id;
        const editedBadge = vouch.updated_at ? '<span style="color: #888; font-size: 11px; margin-left: 8px;">(edited)</span>' : '';

        // Profile photo for vouch user
        const vouchUserId = showEditButton ? vouch.to_user_id : vouch.from_user_id;
        const vouchUsername = showEditButton ? vouch.to_username : vouch.username;
        const photoHTML = vouch.profile_picture_url 
            ? `<div class="vouch-avatar" style="background-image: url(${API_BASE}/api/photo-proxy/${vouch.profile_picture_url}); background-size: cover; background-position: center;"></div>`
            : `<div class="vouch-avatar">👤</div>`;

        // Telegram link
        const telegramLink = vouchUsername ? `https://t.me/${vouchUsername}` : `tg://user?id=${vouchUserId}`;

        return `
        <div class="vouch-item ${isPending ? 'pending' : ''}" data-vouch-id="${vouch.id}">
            <div class="vouch-header">
                <div class="vouch-user-info">
                    <a href="${telegramLink}" target="_blank" class="vouch-avatar-link" title="Open in Telegram">
                        ${photoHTML}
                    </a>
                    <div class="vouch-user-details">
                        <a href="${telegramLink}" target="_blank" class="vouch-user-link" title="Open in Telegram">
                            <span class="vouch-user">${escapeHtml(displayName)}</span>
                        </a>
                        <span class="vouch-date">${formatDate(vouch.created_at)}${editedBadge}</span>
                    </div>
                </div>
            </div>
            ${statusBadge ? `<div style="margin-top: 4px; margin-left: 44px;">${statusBadge}</div>` : ''}
            ${vouch.message ? `<div class="vouch-message" style="margin-left: 44px;">"${sanitizeMessage(vouch.message)}"</div>` : ''}
            ${canEdit ? `
                <div class="vouch-actions" style="margin-left: 44px;">
                    <button class="btn-edit" data-vouch-id="${vouch.id}" data-vouch-message="${escapeHtml(vouch.message || '')}">✏️ Edit</button>
                    <button class="btn-delete" data-vouch-id="${vouch.id}" data-vouch-to="${escapeHtml(displayName)}">🗑️ Delete</button>
                </div>
            ` : ''}
        </div>
        `;
    }).join('');
}

// Vouch Tab
async function loadVouchTab() {
    if (!currentUser) return;

    try {
        const response = await fetch(`${API_BASE}/api/profile/${currentUser.telegram_user_id}`);
        const data = await response.json();

        // Show recent vouches given
        renderRecentVouches(data.vouches_given.slice(0, 5));
    } catch (error) {
        console.error('Error loading vouch tab:', error);
    }
}

function renderRecentVouches(vouches) {
    const container = document.getElementById('recentVouches');

    if (!vouches || vouches.length === 0) {
        container.innerHTML = '<div class="empty-state">No recent vouches</div>';
        return;
    }

    container.innerHTML = vouches.map(vouch => {
        const isPending = vouch.is_pending || !vouch.username;
        const displayName = isPending ? `@${vouch.to_username}` : `@${vouch.username || vouch.first_name}`;
        const statusBadge = isPending ? '<span style="color: #888; font-size: 11px;">⏳ Pending</span>' : '';
        const editedBadge = vouch.updated_at ? '<span style="color: #888; font-size: 11px; margin-left: 8px;">(edited)</span>' : '';

        return `
        <div class="vouch-item ${isPending ? 'pending' : ''}" data-vouch-id="${vouch.id}">
            <div class="vouch-header">
                <span class="vouch-user">${escapeHtml(displayName)}</span>
                <span class="vouch-date">${formatDate(vouch.created_at)}${editedBadge}</span>
            </div>
            ${statusBadge ? `<div style="margin-top: 4px;">${statusBadge}</div>` : ''}
            ${vouch.message ? `<div class="vouch-message">"${sanitizeMessage(vouch.message)}"</div>` : ''}
            <div class="vouch-actions">
                <button class="btn-edit" data-vouch-id="${vouch.id}" data-vouch-message="${escapeHtml(vouch.message || '')}">✏️ Edit</button>
                <button class="btn-delete" data-vouch-id="${vouch.id}" data-vouch-to="${escapeHtml(displayName)}">🗑️ Delete</button>
            </div>
        </div>
        `;
    }).join('');
}

async function handleVouchSubmit(e) {
    e.preventDefault();

    const targetUsername = document.getElementById('targetUsername').value.trim();
    const message = document.getElementById('vouchMessage').value.trim();

    if (!targetUsername) {
        showToast('Please enter a username', 'error');
        return;
    }

    // Note: We no longer block vouches based on content
    // The backend will sanitize the message before storing
    // Everyone can vouch - what gets stored is just cleaned up

    try {
        showLoading(true);

        const voteType = document.getElementById('voteType').value;
        
        const response = await fetch(`${API_BASE}/api/vouch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from_user_id: currentUser.telegram_user_id,
                to_username: targetUsername,
                message: message || null,
                vote_type: voteType
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Check if vouch is pending or confirmed
            if (data.pending) {
                // Pending vouch - user hasn't joined yet
                showToast(`⏳ Vouch saved for @${targetUsername}! They'll receive it when they join the bot.`, 'info');
                triggerHaptic('light');
            } else {
                // Confirmed vouch - user exists
                showToast('✅ Vouch recorded successfully!', 'success');
                triggerHaptic('success');

                // Check for mutual vouch
                if (data.mutual_vouch) {
                    setTimeout(() => {
                        showMutualVouchPrompt(targetUsername);
                    }, 2000);
                }
            }

            // Reset form
            document.getElementById('vouchForm').reset();
            updateCharCount();

            // Reload vouch tab
            loadVouchTab();
        } else {
            showToast(data.detail || 'Failed to submit vouch', 'error');
            triggerHaptic('error');
        }

        showLoading(false);
    } catch (error) {
        console.error('Error submitting vouch:', error);
        showToast('Failed to submit vouch', 'error');
        triggerHaptic('error');
        showLoading(false);
    }
}

function showMutualVouchPrompt(username) {
    showToast(`💬 @${username} also vouched for you! Return the favor?`, 'success');
}

function updateCharCount() {
    const textarea = document.getElementById('vouchMessage');
    const counter = document.getElementById('charCount');
    if (textarea && counter) {
        counter.textContent = textarea.value.length;
    }
}

function checkVouchMessageCompliance(message) {
    const warningDiv = document.getElementById('complianceWarning');
    if (!warningDiv) return;

    if (!message || message.trim().length === 0) {
        warningDiv.style.display = 'none';
        return;
    }

    const compliance = checkMessageCompliance(message);
    if (!compliance.valid) {
        warningDiv.innerHTML = `
            <span style="color: var(--accent-yellow); font-size: 12px;">
                ℹ️ Note: Your message will be sanitized before being stored
            </span>
        `;
        warningDiv.style.display = 'block';
    } else {
        warningDiv.style.display = 'none';
    }
}

// Community Tab
async function loadCommunityTab() {
    // Load based on current view
    if (currentCommunityView === 'activity') {
        await loadActivityFeed();
    } else if (currentCommunityView === 'users') {
        await loadUsersView();
    } else if (currentCommunityView === 'groups') {
        await loadGroupsView();
    } else if (currentCommunityView === 'leaderboards') {
        await loadLeaderboardsView();
    }
}

async function loadActivityFeed() {
    try {
        // Show skeleton instead of loading overlay
        SkeletonHelper.show('activityFeed', 'activityFeed', 5);

        const response = await fetch(`${API_BASE}/api/activity?limit=50`);
        
        if (!response.ok) {
            throw new Error(`Failed to load activity: ${response.status}`);
        }
        
        const data = await response.json();
        renderActivityFeed(data.activity);
    } catch (error) {
        console.error('Error loading activity:', error);
        showToast('Failed to load activity feed', 'error');
        document.getElementById('activityFeed').innerHTML = '<div class="empty-state">Failed to load activity</div>';
    }
}

function renderActivityFeed(activities) {
    const container = document.getElementById('activityFeed');
    
    if (!activities || activities.length === 0) {
        container.innerHTML = '<div class="empty-state">No recent activity</div>';
        return;
    }
    
    container.innerHTML = activities.map(activity => {
        if (activity.activity_type === 'vouch') {
            const fromName = activity.from_username || activity.from_first_name;
            const toName = activity.to_username || activity.to_first_name;
            return `
                <div class="activity-item">
                    <div class="activity-icon">💬</div>
                    <div class="activity-content">
                        <div class="activity-text">
                            <strong>@${escapeHtml(fromName)}</strong> vouched for <strong>@${escapeHtml(toName)}</strong>
                        </div>
                        ${activity.message ? `<div class="activity-message">"${sanitizeMessage(activity.message)}"</div>` : ''}
                        <div class="activity-time">${formatDate(activity.created_at)}</div>
                    </div>
                </div>
            `;
        } else if (activity.activity_type === 'rank_up') {
            const name = activity.username || activity.first_name;
            const newRankEmoji = getRankEmoji(activity.new_rank);
            const newRankName = getRankName(activity.new_rank);
            return `
                <div class="activity-item rank-up">
                    <div class="activity-icon">🎉</div>
                    <div class="activity-content">
                        <div class="activity-text">
                            <strong>@${escapeHtml(name)}</strong> reached <strong>${newRankEmoji} ${newRankName}</strong>
                        </div>
                        <div class="activity-time">${formatDate(activity.created_at)}</div>
                    </div>
                </div>
            `;
        }
        return '';
    }).join('');
}

async function loadUsersView() {
    try {
        // Show skeleton
        SkeletonHelper.show('communityGrid', 'communityGrid', 6);

        const response = await fetch(`${API_BASE}/api/users?limit=100`);

        if (!response.ok) {
            throw new Error(`Failed to load users: ${response.status}`);
        }

        const data = await response.json();
        allUsers = data.users;
        renderCommunityGrid(allUsers);
    } catch (error) {
        console.error('Error loading users:', error);
        showToast('Failed to load users', 'error');
        document.getElementById('communityGrid').innerHTML = '<div class="empty-state">Failed to load users</div>';
    }
}

async function loadGroupsView() {
    try {
        const response = await fetch(`${API_BASE}/api/community-groups`);

        if (!response.ok) {
            throw new Error(`Failed to load groups: ${response.status}`);
        }

        const data = await response.json();
        renderGroupsGrid(data.groups);
    } catch (error) {
        console.error('Error loading groups:', error);
        showToast('Failed to load groups', 'error');
        document.getElementById('groupsGrid').innerHTML = '<div class="empty-state">Failed to load groups</div>';
    }
}

function renderGroupsGrid(groups) {
    const container = document.getElementById('groupsGrid');

    if (!groups || groups.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No community groups available yet.</p>
                <p style="margin-top: 12px; color: var(--text-secondary); font-size: 14px;">
                    Check back soon for new groups to join!
                </p>
            </div>
        `;
        return;
    }

    container.innerHTML = groups.map(group => {
        const memberText = group.member_count ? `${group.member_count.toLocaleString()} members` : 'New group';
        const iconEmoji = group.icon_emoji || '💬';
        const description = group.description || 'Join this community group';

        return `
            <div class="group-card" data-group-link="${escapeHtml(group.telegram_link)}">
                <div class="group-header">
                    <div class="group-icon">${iconEmoji}</div>
                    <div class="group-info">
                        <div class="group-name">${escapeHtml(group.name)}</div>
                        <div class="group-members">${memberText}</div>
                    </div>
                </div>
                <div class="group-description">${escapeHtml(description)}</div>
                <button class="group-join-btn" data-group-link="${escapeHtml(group.telegram_link)}">
                    Join Group →
                </button>
            </div>
        `;
    }).join('');

    // Add click handlers to join buttons and cards
    container.querySelectorAll('.group-join-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const link = btn.dataset.groupLink;
            if (link) {
                openTelegramGroup(link);
            }
        });
    });

    container.querySelectorAll('.group-card').forEach(card => {
        card.addEventListener('click', () => {
            const link = card.dataset.groupLink;
            if (link) {
                openTelegramGroup(link);
            }
        });
    });
}

function openTelegramGroup(link) {
    triggerHaptic('medium');

    // Open Telegram link using Telegram WebApp API if available
    if (tg.openTelegramLink) {
        tg.openTelegramLink(link);
    } else if (tg.openLink) {
        tg.openLink(link);
    } else {
        // Fallback: open in new window
        window.open(link, '_blank');
    }
}

async function loadLeaderboardsView() {
    await loadLeaderboard(currentLeaderboardType);
}

async function loadLeaderboard(boardType) {
    try {
        // Show skeleton
        SkeletonHelper.show('leaderboardContent', 'leaderboard', 5);

        const response = await fetch(`${API_BASE}/api/leaderboards/${boardType}?limit=20`);
        
        if (!response.ok) {
            throw new Error(`Failed to load leaderboard: ${response.status}`);
        }
        
        const data = await response.json();
        renderLeaderboard(data.leaderboard, boardType);
    } catch (error) {
        console.error('Error loading leaderboard:', error);
        showToast('Failed to load leaderboard', 'error');
        document.getElementById('leaderboardContent').innerHTML = '<div class="empty-state">Failed to load leaderboard</div>';
    }
}

function renderLeaderboard(users, boardType) {
    const container = document.getElementById('leaderboardContent');
    
    if (!users || users.length === 0) {
        container.innerHTML = '<div class="empty-state">No data available</div>';
        return;
    }
    
    container.innerHTML = users.map((user, index) => {
        const medals = ['🥇', '🥈', '🥉'];
        const medal = index < 3 ? medals[index] : `${index + 1}.`;
        const name = user.username || user.first_name;
        
        let extraStat = '';
        if (boardType === 'top_givers' && user.vouches_given !== undefined) {
            extraStat = `${user.vouches_given} given`;
        } else if (boardType === 'rising_stars' && user.recent_vouches !== undefined) {
            extraStat = `+${user.recent_vouches} this week`;
        } else if (boardType === 'streak_leaders') {
            extraStat = `🔥 ${user.streak_days} days`;
        } else {
            extraStat = `${user.total_vouches} vouches`;
        }
        
        const photoHTML = user.profile_picture_url 
            ? `<div class="lb-avatar" style="background-image: url(${API_BASE}/api/photo-proxy/${user.profile_picture_url}); background-size: cover; background-position: center; width: 32px; height: 32px; border-radius: 50%; margin-right: 12px;"></div>`
            : `<div class="lb-avatar" style="width: 32px; height: 32px; border-radius: 50%; background: var(--bg-secondary); display: flex; align-items: center; justify-content: center; margin-right: 12px; font-size: 16px;">👤</div>`;
        
        // Telegram link
        const telegramLink = user.username ? `https://t.me/${user.username}` : `tg://user?id=${user.telegram_user_id}`;
        
        return `
            <a href="${telegramLink}" target="_blank" class="leaderboard-item" data-user-id="${user.telegram_user_id}" style="display: flex; align-items: center; text-decoration: none; color: inherit; cursor: pointer;" title="Open in Telegram">
                <div class="lb-position">${medal}</div>
                ${photoHTML}
                <div class="lb-info">
                    <div class="lb-name">@${name}</div>
                    <div class="lb-stat">${user.rank_emoji} ${user.rank_name} • ${extraStat}</div>
                </div>
            </a>
        `;
    }).join('');
}

function renderCommunityGrid(users) {
    const container = document.getElementById('communityGrid');

    if (!users || users.length === 0) {
        container.innerHTML = '<div class="empty-state">No users found</div>';
        return;
    }

    container.innerHTML = users.map(user => {
        const photoHTML = user.profile_picture_url
            ? `<div class="community-avatar" style="background-image: url(${API_BASE}/api/photo-proxy/${user.profile_picture_url}); background-size: cover; background-position: center;"></div>`
            : `<div class="community-avatar">👤</div>`;

        // Dual-metric display
        const reputationPoints = user.reputation_points || 0;
        const behaviorPoints = user.behavior_points || 0;
        const behaviorRankEmoji = user.behavior_rank_emoji || '🧱';

        // Telegram link
        const telegramLink = user.username ? `https://t.me/${user.username}` : `tg://user?id=${user.telegram_user_id}`;

        return `
            <a href="${telegramLink}" target="_blank" class="community-card" data-user-id="${user.telegram_user_id}" style="text-decoration: none; color: inherit; display: block;" title="Open in Telegram">
                ${photoHTML}
                <div class="community-name">@${user.username || user.first_name}</div>
                <div class="community-rank">${user.rank_emoji} ${user.rank_name}</div>
                <div class="community-vouches" style="font-size: 12px; color: var(--text-secondary);">
                    Rep ${reputationPoints.toFixed(1)} • ${behaviorRankEmoji} ${behaviorPoints} pts
                </div>
            </a>
        `;
    }).join('');
}

function filterCommunity() {
    if (currentFilter === 'all') {
        renderCommunityGrid(allUsers);
        return;
    }

    const filtered = allUsers.filter(user => user.rank === currentFilter);
    renderCommunityGrid(filtered);
}

async function handleSearch(e) {
    const query = e.target.value.trim();

    if (query.length < 2) {
        renderCommunityGrid(allUsers);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        renderCommunityGrid(data.users);
    } catch (error) {
        console.error('Search error:', error);
    }
}

// Global search functionality with dropdown
let globalSearchTimeout;
async function handleGlobalSearch(e) {
    const query = e.target.value.trim();
    const dropdown = document.getElementById('searchResultsDropdown');

    // Clear previous timeout
    if (globalSearchTimeout) {
        clearTimeout(globalSearchTimeout);
    }

    // Hide dropdown if query is too short
    if (query.length < 2) {
        dropdown.classList.remove('show');
        return;
    }

    // Debounce search
    globalSearchTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}&limit=10`);
            const data = await response.json();

            renderGlobalSearchResults(data.users);
        } catch (error) {
            console.error('Global search error:', error);
            dropdown.classList.remove('show');
        }
    }, 300);
}

function renderGlobalSearchResults(users) {
    const dropdown = document.getElementById('searchResultsDropdown');

    if (!users || users.length === 0) {
        dropdown.innerHTML = '<div class="search-empty">No users found</div>';
        dropdown.classList.add('show');
        return;
    }

    dropdown.innerHTML = users.map(user => {
        const photoHTML = user.profile_picture_url
            ? `<div class="search-result-avatar" style="background-image: url(${API_BASE}/api/photo-proxy/${user.profile_picture_url}); background-size: cover; background-position: center;"></div>`
            : `<div class="search-result-avatar">👤</div>`;

        return `
            <div class="search-result-item" data-user-id="${user.telegram_user_id}">
                ${photoHTML}
                <div class="search-result-info">
                    <div class="search-result-name">@${escapeHtml(user.username || user.first_name)}</div>
                    <div class="search-result-rank">${user.rank_emoji} ${user.rank_name} • ${user.total_vouches} vouches</div>
                </div>
            </div>
        `;
    }).join('');

    dropdown.classList.add('show');

    // Add click handlers to search results
    dropdown.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const userId = parseInt(item.dataset.userId);
            dropdown.classList.remove('show');
            document.getElementById('globalSearch').value = '';
            loadUserProfile(userId);
        });
    });
}

async function loadUserProfile(userId) {
    try {
        showLoading(true);

        const response = await fetch(`${API_BASE}/api/profile/${userId}`);
        const data = await response.json();

        // Fetch profile photo file_id if not cached
        if (!data.user.profile_picture_url) {
            await fetchAndCacheProfilePhoto(userId);
        }

        const modal = document.getElementById('profileModal');
        const content = document.getElementById('modalProfileContent');

        const rankEmoji = getRankEmoji(data.user.rank);
        const rankName = getRankName(data.user.rank);

        content.innerHTML = `
            <div class="profile-header">
                ${getProfilePhotoHTML(data.user)}
                <div class="profile-info">
                    <h2>@${data.user.username || data.user.first_name}</h2>
                    <div class="rank-badge ${data.user.rank}">${rankEmoji} ${rankName}</div>
                    ${data.user.streak_days > 0 ? `<div class="streak-badge">🔥 ${data.user.streak_days} day streak</div>` : ''}
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${data.user.total_vouches}</div>
                    <div class="stat-label">Vouches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${data.vouches_given.length}</div>
                    <div class="stat-label">Given</div>
                </div>
                ${data.user.streak_days > 0 ? `
                <div class="stat-card streak-card active-streak">
                    <div class="stat-value">🔥 ${data.user.streak_days}</div>
                    <div class="stat-label">Day Streak</div>
                </div>
                ` : ''}
            </div>

            <button class="btn btn-primary btn-large" id="modalVouchBtn" data-username="${escapeHtml(data.user.username || data.user.first_name)}">
                👍 Vouch for this user
            </button>

            <div class="section">
                <h3>Recent Vouches</h3>
                ${data.vouches_received.slice(0, 5).map(vouch => `
                    <div class="vouch-item">
                        <div class="vouch-header">
                            <span class="vouch-user">@${escapeHtml(vouch.username || vouch.first_name)}</span>
                            <span class="vouch-date">${formatDate(vouch.created_at)}</span>
                        </div>
                        ${vouch.message ? `<div class="vouch-message">"${sanitizeMessage(vouch.message)}"</div>` : ''}
                    </div>
                `).join('') || '<div class="empty-state">No vouches yet</div>'}
            </div>
        `;

        modal.classList.add('active');
        showLoading(false);
    } catch (error) {
        console.error('Error loading user profile:', error);
        showToast('Failed to load profile', 'error');
        showLoading(false);
    }
}

function vouchUser(username) {
    document.getElementById('profileModal').classList.remove('active');
    switchTab('vouch');
    document.getElementById('targetUsername').value = username;
    document.getElementById('targetUsername').focus();
}

// Insights Tab (Admin)
async function loadInsightsTab() {
    try {
        showLoading(true);

        const response = await fetch(`${API_BASE}/api/analytics`);
        const data = await response.json();

        // Update overview stats
        document.getElementById('totalUsers').textContent = data.total_users;
        document.getElementById('activeUsers24h').textContent = data.active_users['24h'];
        document.getElementById('totalVouches').textContent = data.total_vouches;
        document.getElementById('newSignups').textContent = data.new_signups_7d;

        // Render rank distribution
        renderRankDistribution(data.rank_distribution);

        // Render leaderboards
        renderLeaderboard('topHelpers', data.top_helpers);
        renderLeaderboard('mostVouched', data.most_vouched);

        showLoading(false);
    } catch (error) {
        console.error('Error loading insights:', error);
        showToast('Failed to load analytics', 'error');
        showLoading(false);
    }
}

function renderRankDistribution(distribution) {
    const container = document.getElementById('rankDistribution');
    const total = distribution.reduce((sum, item) => sum + item.count, 0);

    container.innerHTML = distribution.map(item => {
        const percentage = (item.count / total * 100).toFixed(1);
        const emoji = getRankEmoji(item.rank);
        const name = getRankName(item.rank);

        return `
            <div class="rank-chart-item">
                <span style="min-width: 120px;">${emoji} ${name}</span>
                <div class="rank-chart-bar" style="flex: 1;">
                    <div class="rank-chart-fill" style="width: ${percentage}%"></div>
                </div>
                <span style="min-width: 60px; text-align: right;">${item.count} (${percentage}%)</span>
            </div>
        `;
    }).join('');
}

function renderLeaderboard(containerId, users) {
    const container = document.getElementById(containerId);

    if (!users || users.length === 0) {
        container.innerHTML = '<div class="empty-state">No data yet</div>';
        return;
    }

    container.innerHTML = users.map((user, index) => {
        const emoji = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : `${index + 1}.`;
        const value = user.vouch_count || user.total_vouches;

        return `
            <div class="leaderboard-item">
                <span class="leaderboard-rank">${emoji}</span>
                <div class="leaderboard-info">
                    <div class="leaderboard-name">@${user.username || user.first_name}</div>
                </div>
                <span class="leaderboard-value">${value}</span>
            </div>
        `;
    }).join('');
}

// Profile photo helpers
async function fetchAndCacheProfilePhoto(userId) {
    try {
        const response = await fetch(`${API_BASE}/api/profile-photo/${userId}`);
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.file_id) {
                // Construct secure proxy URL
                const proxyUrl = `${API_BASE}/api/photo-proxy/${data.file_id}`;
                
                // Update currentUser if it's their photo
                if (currentUser && currentUser.telegram_user_id === userId) {
                    currentUser.profile_photo_proxy_url = proxyUrl;
                    updateProfilePhoto();
                }
                return proxyUrl;
            }
        }
    } catch (error) {
        console.error(`Failed to fetch profile photo for user ${userId}:`, error);
    }
    return null;
}

function updateProfilePhoto() {
    const avatarElements = document.querySelectorAll('.avatar');
    avatarElements.forEach(el => {
        if (currentUser && currentUser.profile_photo_proxy_url) {
            el.style.backgroundImage = `url(${currentUser.profile_photo_proxy_url})`;
            el.style.backgroundSize = 'cover';
            el.style.backgroundPosition = 'center';
            el.textContent = '';
        }
    });
}

function getProfilePhotoHTML(user) {
    if (user && user.profile_picture_url) {
        // profile_picture_url contains file_id, construct proxy URL
        const proxyUrl = `${API_BASE}/api/photo-proxy/${user.profile_picture_url}`;
        return `<div class="avatar" style="background-image: url(${proxyUrl}); background-size: cover; background-position: center;"></div>`;
    }
    return `<div class="avatar">👤</div>`;
}

// Profile Actions
async function handleRequestVouch() {
    const shareUrl = `https://t.me/${botUsername}?startapp=profile_${currentUser.telegram_user_id}`;

    if (tg.isVersionAtLeast('6.1')) {
        tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent('Please vouch for me on Vouch Portal!')}`);
    } else {
        // Fallback: copy to clipboard
        await navigator.clipboard.writeText(shareUrl);
        showToast('Link copied to clipboard!', 'success');
    }

    // Log event
    await fetch(`${API_BASE}/api/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: currentUser.telegram_user_id,
            platform: 'telegram'
        })
    });
}

async function handleShareProfile() {
    const rankEmoji = getRankEmoji(currentUser.rank);
    const rankName = getRankName(currentUser.rank);
    const shareText = `I just reached ${rankEmoji} ${rankName} on Vouch Portal! Build yours: https://t.me/VouchPortalBot?startapp=ref_${currentUser.telegram_user_id}`;

    if (tg.isVersionAtLeast('6.1')) {
        tg.openTelegramLink(`https://t.me/share/url?text=${encodeURIComponent(shareText)}`);
    } else {
        await navigator.clipboard.writeText(shareText);
        showToast('Share text copied to clipboard!', 'success');
    }

    // Log event
    await fetch(`${API_BASE}/api/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            user_id: currentUser.telegram_user_id,
            platform: 'share'
        })
    });
}

// Header Badge
function updateHeaderBadge() {
    if (!currentUser) return;

    const badge = document.getElementById('userBadge');
    const emoji = getRankEmoji(currentUser.rank);
    badge.textContent = `${emoji} ${currentUser.total_vouches} vouches`;
}

// Utility Functions
function getRankEmoji(rank) {
    const emojis = {
        'unverified': '🚫',
        'verified': '✅',
        'trusted': '🔷',
        'endorsed': '🛡',
        'top_tier': '👑'
    };
    return emojis[rank] || '❓';
}

function getRankName(rank) {
    const names = {
        'unverified': 'Unverified',
        'verified': 'Verified',
        'trusted': 'Trusted',
        'endorsed': 'Endorsed',
        'top_tier': 'Top-Tier'
    };
    return names[rank] || 'Unknown';
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

// Profile Editing
async function openEditProfileModal() {
    try {
        // Fetch current profile
        const response = await fetch(`${API_BASE}/api/profile/${currentUser.telegram_user_id}`);
        const data = await response.json();
        
        // Populate form with current values
        document.getElementById('editBio').value = data.user.bio || '';
        document.getElementById('editLocation').value = data.user.location || '';
        document.getElementById('bioCharCount').textContent = (data.user.bio || '').length;
        
        // Show modal
        document.getElementById('editProfileModal').classList.add('active');
    } catch (error) {
        console.error('Error opening edit profile:', error);
        showToast('Failed to load profile for editing', 'error');
    }
}

async function handleProfileUpdate(e) {
    e.preventDefault();
    
    const bio = document.getElementById('editBio').value.trim();
    const location = document.getElementById('editLocation').value.trim();
    
    try {
        showLoading(true);

        const response = await fetch(`${API_BASE}/api/profile`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                telegram_user_id: currentUser.telegram_user_id,
                bio: bio || null,
                location: location || null
            })
        });
        
        if (response.ok) {
            showToast('✅ Profile updated successfully!', 'success');
            document.getElementById('editProfileModal').classList.remove('active');
            
            // Reload profile tab
            await loadProfileTab();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to update profile', 'error');
        }
    } catch (error) {
        console.error('Error updating profile:', error);
        showToast('Failed to update profile', 'error');
    } finally {
        showLoading(false);
    }
}

// Edit Vouch functionality
let currentEditVouchId = null;

function openEditVouchModal(vouchId, currentMessage) {
    currentEditVouchId = vouchId;
    
    // Populate form with current message
    const textarea = document.getElementById('editVouchMessage');
    textarea.value = currentMessage || '';
    document.getElementById('editVouchCharCount').textContent = currentMessage.length;
    
    // Show modal
    document.getElementById('editVouchModal').classList.add('active');
}

// Delete vouch functionality
async function handleDeleteVouch(vouchId, vouchTo) {
    // Confirm deletion
    const confirmed = confirm(`Are you sure you want to delete your vouch for ${vouchTo}? This action cannot be undone.`);

    if (!confirmed) {
        return;
    }

    try {
        showLoading(true);

        const response = await fetch(`${API_BASE}/api/vouches/${vouchId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from_user_id: currentUser.telegram_user_id
            })
        });

        if (response.ok) {
            showToast('✅ Vouch deleted successfully!', 'success');
            triggerHaptic('success');

            // Reload the current tab to show updated vouches
            if (currentTab === 'profile') {
                await loadProfileTab();
            } else if (currentTab === 'vouch') {
                await loadVouchTab();
            }
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to delete vouch', 'error');
            triggerHaptic('error');
        }
    } catch (error) {
        console.error('Error deleting vouch:', error);
        showToast('Failed to delete vouch', 'error');
        triggerHaptic('error');
    } finally {
        showLoading(false);
    }
}

async function handleEditVouchSubmit(e) {
    e.preventDefault();

    if (!currentEditVouchId) {
        showToast('Error: No vouch selected', 'error');
        return;
    }

    const message = document.getElementById('editVouchMessage').value.trim();

    try {
        showLoading(true);

        const response = await fetch(`${API_BASE}/api/vouches/${currentEditVouchId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from_user_id: currentUser.telegram_user_id,
                message: message
            })
        });

        if (response.ok) {
            showToast('✅ Vouch updated successfully!', 'success');
            document.getElementById('editVouchModal').classList.remove('active');

            // Reload the current tab to show updated vouch
            if (currentTab === 'profile') {
                await loadProfileTab();
            } else if (currentTab === 'vouch') {
                await loadVouchTab();
            }

            currentEditVouchId = null;
        } else {
            const error = await response.json();
            showToast(error.detail || 'Failed to update vouch', 'error');
        }
    } catch (error) {
        console.error('Error updating vouch:', error);
        showToast('Failed to update vouch', 'error');
    } finally {
        showLoading(false);
    }
}

// Handle visibility change (refresh data when tab becomes visible)
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && currentUser) {
        loadProfileTab();
    }
});

// Share Modal Functions
async function copyShareLink() {
    const shareLink = document.getElementById('shareLink').value;
    try {
        await navigator.clipboard.writeText(shareLink);
        showToast('✅ Link copied to clipboard!', 'success');
    } catch (error) {
        console.error('Error copying link:', error);
        showToast('Failed to copy link', 'error');
    }
}

function shareOnTelegram() {
    const modal = document.getElementById('shareModal');
    const shareText = modal.dataset.shareText;
    const shareLink = modal.dataset.shareLink;
    
    if (tg.isVersionAtLeast && tg.isVersionAtLeast('6.1')) {
        tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(shareLink)}&text=${encodeURIComponent(shareText)}`);
    } else {
        tg.openLink(`https://t.me/share/url?url=${encodeURIComponent(shareLink)}&text=${encodeURIComponent(shareText)}`);
    }
    
    modal.classList.remove('active');
}

// Mutual Vouch CTA
let mutualVouchUsername = null;

function showMutualVouchCTA(username) {
    mutualVouchUsername = username;
    document.getElementById('mutualVouchMessage').textContent = `💬 @${username} vouched for you! Return the favor?`;
    
    const toast = document.getElementById('mutualVouchToast');
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 8000);
}

function handleReturnVouch() {
    if (mutualVouchUsername) {
        document.getElementById('mutualVouchToast').classList.remove('active');
        switchTab('vouch');
        document.getElementById('targetUsername').value = mutualVouchUsername;
        document.getElementById('targetUsername').focus();
        mutualVouchUsername = null;
    }
}

// Telegram WebApp theme
if (tg.colorScheme === 'dark') {
    document.body.classList.add('dark-theme');
}
