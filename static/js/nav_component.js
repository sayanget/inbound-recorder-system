/**
 * Universal Navigation Component
 * Injects a consistent navigation menu into #nav-container
 */
(function() {
    const navConfig = [
        { name: '首页', lang: 'home', url: '/', icon: 'fa-home' },
        { name: '分拣录入', lang: 'sorting_entry', url: '/sorting', icon: 'fa-boxes', class: 'nav-item-sorting', page: 'sorting' },
        { name: '统计数据', lang: 'statistics_data', url: '/statistics', icon: 'fa-chart-bar', class: 'nav-item-stats', page: 'statistics' },
        { name: '历史查询', lang: 'history_query', url: '/history', icon: 'fa-history', class: 'nav-item-history', page: 'history' },
        { name: '产能计划', lang: 'capacity_planning', url: '/sorting-schedule', icon: 'fa-calendar-alt', class: 'nav-item-schedule', page: 'sorting-schedule' },
        { name: '出库统计', lang: 'outbound_stats', url: '/outbound-stats', icon: 'fa-truck', class: 'nav-item-outbound', page: 'outbound-stats' },
        { name: '排班 vs 集包', lang: 'schedule_packaging', url: '/schedule-packaging', icon: 'fa-layer-group', class: 'nav-item-schedule-pack', page: 'outbound-stats' },
        { name: '生产及耗材', lang: 'consumables', url: '/consumables', icon: 'fa-box', class: 'nav-item-cost', page: 'consumables' },
        { name: '操作日志', lang: 'operation_logs', url: '/logs', icon: 'fa-file-alt', class: 'nav-item-logs', page: 'logs', hidden: true },
        { name: '基础设置', lang: 'admin_settings', url: '/admin', icon: 'fa-cog', class: 'nav-item-admin', page: 'admin', hidden: true },
        { name: '成本核算', lang: 'cost_accounting', url: '/cost_accounting', icon: 'fa-calculator', class: 'nav-item-cost-acct', page: 'cost_accounting', hidden: true }
    ];

    function initNav() {
        const container = document.getElementById('nav-container');
        if (!container) return;

        // Add CSS if not present
        if (!document.getElementById('universal-nav-styles')) {
            const link = document.createElement('link');
            link.id = 'universal-nav-styles';
            link.rel = 'stylesheet';
            link.href = '/static/css/nav_styles.css';
            document.head.appendChild(link);
        }

        const currentPath = window.location.pathname;
        let navHtml = `
            <header class="header-main">
                <div class="header-top">
                    <h1><i class="fas fa-truck-loading"></i> <span data-lang="app_title">仓库综合分析看板</span></h1>
                    <div class="header-actions">
                        <div class="user-info-universal">
                            <i class="fas fa-user-circle"></i>
                            <span id="nav-usernameDisplay">加载中...</span>
                            <button id="nav-logoutBtn" class="logout-btn-nav" title="Logout">
                                <i class="fas fa-sign-out-alt"></i>
                            </button>
                        </div>
                        <div class="settings-nav">
                            <button class="theme-toggle-nav" id="nav-themeToggle" title="Toggle Theme">
                                <i class="fas fa-moon"></i>
                            </button>
                            <div class="lang-selector-nav">
                                <button class="lang-btn-nav" id="nav-langBtn">
                                    <span id="nav-currentLang">ZH</span>
                                    <i class="fas fa-chevron-down"></i>
                                </button>
                                <div class="lang-dropdown-nav" id="nav-langDropdown">
                                    <a href="#" class="lang-opt-nav" data-lang-code="zh">中文</a>
                                    <a href="#" class="lang-opt-nav" data-lang-code="en">English</a>
                                    <a href="#" class="lang-opt-nav" data-lang-code="es">Español</a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <nav class="universal-nav">
        `;

        navConfig.forEach(item => {
            const isActive = currentPath === item.url || (item.url === '/' && currentPath === '/index.html') ? 'active' : '';
            const hideStyle = item.hidden ? 'style="display:none;"' : '';
            navHtml += `
                <a href="${item.url}" class="nav-item ${item.class || ''} ${isActive}" ${hideStyle} data-nav-id="${item.lang}">
                    <i class="fas ${item.icon}"></i>
                    <span data-lang="${item.lang}">${item.name}</span>
                </a>
            `;
        });

        navHtml += `
                </nav>
            </header>
        `;
        container.innerHTML = navHtml;

        // --- Event Listeners and Functionality ---
        
        // Logout functionality
        const logoutBtn = document.getElementById('nav-logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                fetch('/api/logout', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                }).then(() => window.location.href = '/login');
            });
        }

        // Theme Toggle
        const themeBtn = document.getElementById('nav-themeToggle');
        if (themeBtn && window.themeToggle) {
            themeBtn.addEventListener('click', () => {
                window.themeToggle.toggle();
                updateThemeIcon();
            });
        }

        function updateThemeIcon() {
            const icon = themeBtn ? themeBtn.querySelector('i') : null;
            if (icon) {
                const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
                icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
            }
        }
        updateThemeIcon();

        // Language Dropdown
        const langBtn = document.getElementById('nav-langBtn');
        const langDropdown = document.getElementById('nav-langDropdown');
        if (langBtn && langDropdown) {
            langBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                langDropdown.classList.toggle('show');
            });
            document.addEventListener('click', () => langDropdown.classList.remove('show'));
        }

        // Language Switching
        document.querySelectorAll('.lang-opt-nav').forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.preventDefault();
                const code = opt.getAttribute('data-lang-code');
                if (window.setLanguage) {
                    window.setLanguage(code);
                    localStorage.setItem('preferred_language', code);
                    updateLangDisplay(code);
                } else if (window.changeLanguage) {
                    // Fallback for any pages using the old name
                    window.changeLanguage(code);
                    localStorage.setItem('preferred_language', code);
                    updateLangDisplay(code);
                }
            });
        });

        function updateLangDisplay(code) {
            const display = document.getElementById('nav-currentLang');
            if (display) display.textContent = code.toUpperCase();
        }
        
        const savedLang = localStorage.getItem('preferred_language') || 'zh';
        updateLangDisplay(savedLang);

        // Check login and permissions
        fetch('/api/check_login')
            .then(r => r.json())
            .then(data => {
                if (data.logged_in) {
                    const userDisplay = document.getElementById('nav-usernameDisplay');
                    if (userDisplay) userDisplay.textContent = data.user.username;
                    
                    const role = data.user.role;
                    const username = data.user.username;
                    const isPrivileged = role === 'admin' || role === 'boss';
                    
                    if (isPrivileged) {
                        // Admin/boss see nav items, but some are restricted to admin account only
                        document.querySelectorAll('.nav-item[data-nav-id]').forEach(btn => {
                            const navId = btn.getAttribute('data-nav-id');
                            // Specifically restrict operation logs and admin settings to 'admin' account
                            if ((navId === 'operation_logs' || navId === 'admin_settings') && username !== 'admin') {
                                btn.style.display = 'none';
                            } else {
                                btn.style.display = 'inline-flex';
                            }
                        });
                    } else {
                        // Fetch per-page permissions for regular users
                        fetch('/api/user_permissions')
                            .then(r => r.json())
                            .then(permissions => {
                                navConfig.forEach(item => {
                                    if (!item.page) return; // no page key = always visible (e.g. 首页)
                                    const el = document.querySelector(`.nav-item[data-nav-id="${item.lang}"]`);
                                    if (!el) return;
                                    const perm = permissions[item.page];
                                    if (perm && perm.can_view) {
                                        // Still respect the global admin restriction for these items if they were somehow granted
                                        if ((item.lang === 'operation_logs' || item.lang === 'admin_settings') && username !== 'admin') {
                                            el.style.display = 'none';
                                        } else {
                                            el.style.display = 'inline-flex';
                                        }
                                    } else {
                                        el.style.display = 'none';
                                    }
                                });
                            })
                            .catch(err => console.error('Permissions fetch failed:', err));
                    }
                } else if (!window.location.pathname.includes('/login')) {
                    window.location.href = '/login';
                }
            })
            .catch(err => console.error('Nav check failed:', err));
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNav);
    } else {
        initNav();
    }
})();
