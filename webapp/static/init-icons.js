// Icon Initialization Script
// This script injects SVG icons into placeholder elements throughout the UI

(function() {
    'use strict';

    // Wait for DOM and icons.js to load
    function initIcons() {
        if (typeof Icons === 'undefined') {
            console.warn('Icons library not loaded yet, retrying...');
            setTimeout(initIcons, 100);
            return;
        }

        // Edit Profile Button
        const editBtn = document.querySelector('#editProfileBtn');
        if (editBtn && !editBtn.querySelector('svg')) {
            editBtn.innerHTML = Icons.edit;
        }

        // Location Icon
        const locationIcon = document.querySelector('.location-icon');
        if (locationIcon && !locationIcon.querySelector('svg')) {
            locationIcon.innerHTML = Icons.mapPin;
        }

        // Stat Card Icons
        const statCards = document.querySelectorAll('.stat-card');
        statCards.forEach(card => {
            const iconEl = card.querySelector('.stat-icon');
            if (!iconEl || iconEl.querySelector('svg')) return;

            if (card.classList.contains('positive-votes')) {
                iconEl.innerHTML = Icons.thumbsUp;
            } else if (card.classList.contains('negative-votes')) {
                iconEl.innerHTML = Icons.thumbsDown;
            } else if (card.classList.contains('streak-card')) {
                iconEl.innerHTML = Icons.flame;
            }
        });

        // Action Button Icons
        const requestVouchBtn = document.querySelector('#requestVouchBtn .btn-icon-left');
        if (requestVouchBtn && !requestVouchBtn.querySelector('svg')) {
            requestVouchBtn.innerHTML = Icons.messageCircle;
        }

        const shareProfileBtn = document.querySelector('#shareProfileBtn .btn-icon-left');
        if (shareProfileBtn && !shareProfileBtn.querySelector('svg')) {
            shareProfileBtn.innerHTML = Icons.share;
        }

        // Vote Button Icons
        const voteButtons = document.querySelectorAll('.vote-btn');
        voteButtons.forEach(btn => {
            const iconEl = btn.querySelector('.vote-icon');
            if (!iconEl || iconEl.querySelector('svg')) return;

            if (btn.classList.contains('vote-positive')) {
                iconEl.innerHTML = Icons.thumbsUp;
            } else if (btn.classList.contains('vote-negative')) {
                iconEl.innerHTML = Icons.thumbsDown;
            }
        });

        // Disclaimer Icon
        const disclaimerIcon = document.querySelector('.disclaimer-icon');
        if (disclaimerIcon && !disclaimerIcon.querySelector('svg')) {
            disclaimerIcon.innerHTML = Icons.alertCircle;
        }

        // Submit Vote Button Icon
        const submitVouchBtn = document.querySelector('#submitVouchBtn .btn-icon-left');
        if (submitVouchBtn && !submitVouchBtn.querySelector('svg')) {
            submitVouchBtn.innerHTML = Icons.check;
        }

        // Community View Tab Icons
        const viewTabs = document.querySelectorAll('.view-tab-btn');
        viewTabs.forEach(tab => {
            const iconEl = tab.querySelector('.tab-icon');
            if (!iconEl || iconEl.querySelector('svg')) return;

            const view = tab.dataset.view;
            if (view === 'activity') {
                iconEl.innerHTML = Icons.activity;
            } else if (view === 'users') {
                iconEl.innerHTML = Icons.users;
            } else if (view === 'leaderboards') {
                iconEl.innerHTML = Icons.trophy;
            }
        });

        // Search Icon
        const searchIcon = document.querySelector('.search-icon');
        if (searchIcon && !searchIcon.querySelector('svg')) {
            searchIcon.innerHTML = Icons.search;
        }

        // Filter Button Icons
        const filterButtons = document.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            const iconEl = btn.querySelector('.filter-icon');
            if (!iconEl || iconEl.querySelector('svg')) return;

            const filter = btn.dataset.filter;
            if (filter === 'top_tier') {
                iconEl.innerHTML = Icons.crown;
            } else if (filter === 'endorsed') {
                iconEl.innerHTML = Icons.shield;
            } else if (filter === 'trusted') {
                iconEl.innerHTML = Icons.verified;
            }
        });

        // Save Changes Button Icons (all modals)
        const saveButtons = document.querySelectorAll('.btn-primary.btn-large .btn-icon-left');
        saveButtons.forEach(btn => {
            if (!btn.querySelector('svg')) {
                btn.innerHTML = Icons.save;
            }
        });

        // Copy Link Button
        const copyLinkBtn = document.querySelector('#copyLinkBtn .btn-icon-left');
        if (copyLinkBtn && !copyLinkBtn.querySelector('svg')) {
            copyLinkBtn.innerHTML = Icons.copy;
        }

        // Telegram Share Button
        const telegramShareBtn = document.querySelector('#telegramShareBtn .btn-icon-left');
        if (telegramShareBtn && !telegramShareBtn.querySelector('svg')) {
            telegramShareBtn.innerHTML = Icons.send;
        }

        // Modal Close Buttons
        const closeButtons = document.querySelectorAll('.modal .close');
        closeButtons.forEach(btn => {
            if (!btn.querySelector('svg') && btn.textContent === '×') {
                btn.innerHTML = Icons.x;
            }
        });

        console.log('✓ Icons initialized successfully');
    }

    // Re-initialize icons when content changes (for dynamic content)
    function observeContentChanges() {
        if (typeof MutationObserver === 'undefined') return;

        const observer = new MutationObserver((mutations) => {
            let shouldReinitialize = false;

            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    // Check if any added nodes have icon placeholders
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            if (node.querySelector && (
                                node.querySelector('.btn-icon-left') ||
                                node.querySelector('.stat-icon') ||
                                node.querySelector('.vote-icon') ||
                                node.classList?.contains('btn-icon-left')
                            )) {
                                shouldReinitialize = true;
                            }
                        }
                    });
                }
            });

            if (shouldReinitialize) {
                setTimeout(initIcons, 50); // Debounce re-initialization
            }
        });

        // Observe the main content area for changes
        const contentArea = document.querySelector('.content');
        if (contentArea) {
            observer.observe(contentArea, {
                childList: true,
                subtree: true
            });
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initIcons();
            observeContentChanges();
        });
    } else {
        initIcons();
        observeContentChanges();
    }

    // Export reinit function for manual calls
    window.reinitializeIcons = initIcons;
})();
