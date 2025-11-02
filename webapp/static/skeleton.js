// Loading Skeleton Helper Module
// Provides skeleton screen templates for better mobile UX

const SkeletonScreens = {
    // Profile Loading Skeleton
    profile: () => `
        <div class="profile-card skeleton-profile">
            <div class="skeleton-profile-header">
                <div class="skeleton skeleton-avatar"></div>
                <div class="skeleton-profile-info">
                    <div class="skeleton skeleton-text large" style="width: 60%;"></div>
                    <div class="skeleton skeleton-text" style="width: 40%; margin-top: 8px;"></div>
                </div>
            </div>

            <div class="skeleton-stats-grid">
                <div class="skeleton skeleton-stat-card"></div>
                <div class="skeleton skeleton-stat-card"></div>
                <div class="skeleton skeleton-stat-card"></div>
            </div>

            <div class="skeleton skeleton-text" style="width: 100%; height: 12px; margin-bottom: 16px;"></div>

            <div style="display: flex; gap: 12px;">
                <div class="skeleton skeleton-button" style="flex: 1;"></div>
                <div class="skeleton skeleton-button" style="flex: 1;"></div>
            </div>
        </div>
    `,

    // Vouch List Skeleton
    vouchList: (count = 3) => {
        let items = '';
        for (let i = 0; i < count; i++) {
            items += `
                <div class="skeleton-vouch-item">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                        <div class="skeleton skeleton-text" style="width: 30%;"></div>
                        <div class="skeleton skeleton-text small" style="width: 20%;"></div>
                    </div>
                    <div class="skeleton skeleton-text" style="width: 80%;"></div>
                    <div class="skeleton skeleton-text small" style="width: 60%;"></div>
                </div>
            `;
        }
        return `<div class="skeleton-vouch-list">${items}</div>`;
    },

    // Community Grid Skeleton
    communityGrid: (count = 6) => {
        let items = '';
        for (let i = 0; i < count; i++) {
            items += `
                <div class="skeleton-community-card">
                    <div class="skeleton skeleton-community-avatar"></div>
                    <div class="skeleton skeleton-text" style="width: 70%; margin: 0 auto 8px;"></div>
                    <div class="skeleton skeleton-text small" style="width: 50%; margin: 0 auto 4px;"></div>
                    <div class="skeleton skeleton-text small" style="width: 40%; margin: 0 auto;"></div>
                </div>
            `;
        }
        return `<div class="skeleton-community-grid">${items}</div>`;
    },

    // Activity Feed Skeleton
    activityFeed: (count = 5) => {
        let items = '';
        for (let i = 0; i < count; i++) {
            items += `
                <div class="activity-item" style="pointer-events: none;">
                    <div class="activity-icon">
                        <div class="skeleton skeleton-circle" style="width: 24px; height: 24px;"></div>
                    </div>
                    <div class="activity-content" style="flex: 1;">
                        <div class="skeleton skeleton-text" style="width: 85%;"></div>
                        <div class="skeleton skeleton-text small" style="width: 30%; margin-top: 4px;"></div>
                    </div>
                </div>
            `;
        }
        return `<div class="activity-feed">${items}</div>`;
    },

    // Leaderboard Skeleton
    leaderboard: (count = 5) => {
        let items = '';
        for (let i = 0; i < count; i++) {
            items += `
                <div class="leaderboard-item" style="pointer-events: none;">
                    <div class="skeleton skeleton-circle" style="width: 40px; height: 40px;"></div>
                    <div style="flex: 1;">
                        <div class="skeleton skeleton-text" style="width: 50%;"></div>
                        <div class="skeleton skeleton-text small" style="width: 30%; margin-top: 4px;"></div>
                    </div>
                    <div class="skeleton skeleton-text" style="width: 40px;"></div>
                </div>
            `;
        }
        return `<div class="leaderboard-list">${items}</div>`;
    },

    // Stats Overview Skeleton (for Insights tab)
    statsOverview: () => `
        <div class="stats-overview">
            <div class="insight-card">
                <div class="skeleton skeleton-text large" style="width: 60%; margin: 0 auto 8px;"></div>
                <div class="skeleton skeleton-text small" style="width: 40%; margin: 0 auto;"></div>
            </div>
            <div class="insight-card">
                <div class="skeleton skeleton-text large" style="width: 60%; margin: 0 auto 8px;"></div>
                <div class="skeleton skeleton-text small" style="width: 40%; margin: 0 auto;"></div>
            </div>
            <div class="insight-card">
                <div class="skeleton skeleton-text large" style="width: 60%; margin: 0 auto 8px;"></div>
                <div class="skeleton skeleton-text small" style="width: 40%; margin: 0 auto;"></div>
            </div>
            <div class="insight-card">
                <div class="skeleton skeleton-text large" style="width: 60%; margin: 0 auto 8px;"></div>
                <div class="skeleton skeleton-text small" style="width: 40%; margin: 0 auto;"></div>
            </div>
        </div>
    `
};

// Helper functions to show/hide skeletons
const SkeletonHelper = {
    show: (elementId, skeletonType, ...args) => {
        const element = document.getElementById(elementId);
        if (!element) return;

        const skeletonFunc = SkeletonScreens[skeletonType];
        if (skeletonFunc) {
            element.innerHTML = skeletonFunc(...args);
        }
    },

    hide: (elementId) => {
        // Just a marker function - actual content will replace skeleton
    },

    // Show skeleton in a container
    showIn: (containerId, skeletonHtml) => {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = skeletonHtml;
        }
    }
};

// Export for global use
if (typeof window !== 'undefined') {
    window.SkeletonScreens = SkeletonScreens;
    window.SkeletonHelper = SkeletonHelper;
}
