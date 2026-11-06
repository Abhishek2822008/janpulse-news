/**
 * JanPulse Public Front-End Script
 * Handles bilingual switching, AJAX Likes, Bookmarks, Comments, and Local News Cascade
 */

document.addEventListener('DOMContentLoaded', () => {
    initMobileMenu();
    initLocationFilter();
    initInteractiveActions();
    initShareButtons();
    updateLiveDateTime();
});

// 1. Mobile Menu Toggle
function initMobileMenu() {
    const toggleBtn = document.getElementById('mobile-menu-btn');
    const drawer = document.getElementById('mobile-drawer');
    const closeBtn = document.getElementById('close-mobile-drawer');
    const overlay = document.getElementById('mobile-drawer-overlay');

    if (toggleBtn && drawer) {
        toggleBtn.addEventListener('click', () => {
            drawer.classList.remove('translate-x-full');
            if (overlay) overlay.classList.remove('hidden');
        });
    }

    const closeDrawer = () => {
        if (drawer) drawer.classList.add('translate-x-full');
        if (overlay) overlay.classList.add('hidden');
    };

    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    if (overlay) overlay.addEventListener('click', closeDrawer);
}

// 2. Interactive Likes & Bookmarks (AJAX)
function initInteractiveActions() {
    // Like Button
    document.querySelectorAll('.btn-like-news').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const newsId = btn.getAttribute('data-news-id');
            const countSpan = btn.querySelector('.like-count');
            const icon = btn.querySelector('.like-icon');

            try {
                const response = await fetch(`/api/news/${newsId}/like`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.status === 401) {
                    showToast('Please login to like this article', 'warning');
                    setTimeout(() => {
                        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
                    }, 1200);
                    return;
                }

                const data = await response.json();
                if (data.success) {
                    if (countSpan) countSpan.textContent = data.likes_count;
                    if (data.liked) {
                        btn.classList.add('text-rose-600', 'font-semibold');
                        if (icon) icon.classList.add('fill-current');
                        showToast('Article liked!', 'success');
                    } else {
                        btn.classList.remove('text-rose-600', 'font-semibold');
                        if (icon) icon.classList.remove('fill-current');
                        showToast('Article unliked', 'info');
                    }
                }
            } catch (err) {
                console.error('Like error:', err);
            }
        });
    });

    // Bookmark Button
    document.querySelectorAll('.btn-bookmark-news').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            const newsId = btn.getAttribute('data-news-id');
            const icon = btn.querySelector('.bookmark-icon');
            const textSpan = btn.querySelector('.bookmark-text');

            try {
                const response = await fetch(`/api/news/${newsId}/bookmark`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.status === 401) {
                    showToast('Please login to save articles', 'warning');
                    setTimeout(() => {
                        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
                    }, 1200);
                    return;
                }

                const data = await response.json();
                if (data.success) {
                    if (data.bookmarked) {
                        btn.classList.add('text-amber-600', 'bg-amber-50');
                        if (icon) icon.classList.add('fill-current');
                        if (textSpan) textSpan.textContent = textSpan.getAttribute('data-saved-text') || 'Saved';
                        showToast('Saved to your reading list!', 'success');
                    } else {
                        btn.classList.remove('text-amber-600', 'bg-amber-50');
                        if (icon) icon.classList.remove('fill-current');
                        if (textSpan) textSpan.textContent = textSpan.getAttribute('data-save-text') || 'Bookmark';
                        showToast('Removed from reading list', 'info');
                        
                        // If on saved articles page, remove the card smoothly
                        const savedCard = document.getElementById(`saved-card-${newsId}`);
                        if (savedCard) {
                            savedCard.style.opacity = '0';
                            setTimeout(() => savedCard.remove(), 300);
                        }
                    }
                }
            } catch (err) {
                console.error('Bookmark error:', err);
            }
        });
    });
}

// 3. Local News Cascade Selector (State -> District -> City)
function initLocationFilter() {
    const stateSelect = document.getElementById('local-state-select');
    const districtSelect = document.getElementById('local-district-select');
    const citySelect = document.getElementById('local-city-select');

    if (!stateSelect) return;

    stateSelect.addEventListener('change', async () => {
        const selectedState = stateSelect.value;
        districtSelect.innerHTML = '<option value="">All Districts</option>';
        citySelect.innerHTML = '<option value="">All Cities</option>';
        districtSelect.disabled = !selectedState;
        citySelect.disabled = true;

        if (selectedState) {
            try {
                const res = await fetch(`/api/locations/districts?state=${encodeURIComponent(selectedState)}`);
                const data = await res.json();
                data.districts.forEach(dist => {
                    const opt = document.createElement('option');
                    opt.value = dist;
                    opt.textContent = dist;
                    districtSelect.appendChild(opt);
                });
                districtSelect.disabled = false;
            } catch (err) {
                console.error('Error fetching districts:', err);
            }
        }
    });

    if (districtSelect) {
        districtSelect.addEventListener('change', async () => {
            const selectedState = stateSelect.value;
            const selectedDistrict = districtSelect.value;
            citySelect.innerHTML = '<option value="">All Cities</option>';
            citySelect.disabled = !selectedDistrict;

            if (selectedDistrict) {
                try {
                    const res = await fetch(`/api/locations/cities?state=${encodeURIComponent(selectedState)}&district=${encodeURIComponent(selectedDistrict)}`);
                    const data = await res.json();
                    data.cities.forEach(city => {
                        const opt = document.createElement('option');
                        opt.value = city;
                        opt.textContent = city;
                        citySelect.appendChild(opt);
                    });
                    citySelect.disabled = false;
                } catch (err) {
                    console.error('Error fetching cities:', err);
                }
            }
        });
    }
}

// 4. Social Sharing & Clipboard
function initShareButtons() {
    document.querySelectorAll('.btn-share-copy').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            navigator.clipboard.writeText(window.location.href).then(() => {
                showToast('Article link copied to clipboard!', 'success');
            }).catch(() => {
                showToast('Could not copy link', 'warning');
            });
        });
    });
}

// 5. Toast Notification System
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed bottom-5 right-5 z-50 flex flex-col space-y-2 pointer-events-none';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const bgColors = {
        success: 'bg-emerald-600 text-white',
        warning: 'bg-amber-600 text-white',
        danger: 'bg-rose-600 text-white',
        info: 'bg-slate-900 text-white'
    };

    toast.className = `${bgColors[type] || bgColors.info} px-4 py-3 rounded-lg shadow-xl text-sm font-medium flex items-center space-x-2 transition-all transform duration-300 pointer-events-auto opacity-0 translate-y-3`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove('opacity-0', 'translate-y-3');
    });

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-3');
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}

// 6. Live Time Display in Top Header
function updateLiveDateTime() {
    const el = document.getElementById('live-datetime');
    if (!el) return;

    const render = () => {
        const now = new Date();
        const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true };
        el.textContent = now.toLocaleDateString('en-IN', options);
    };
    render();
    setInterval(render, 30000);
}
