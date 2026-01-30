const themeToggle = {
    init: function () {
        // Retrieve saved theme or detect system preference
        const savedTheme = localStorage.getItem('theme');
        const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        // Use saved theme, or fallback to system preference
        const themeToApply = savedTheme || (systemDark ? 'dark' : 'light');

        this.applyTheme(themeToApply);

        // Listen for system preference changes if no user preference is set
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            if (!localStorage.getItem('theme')) {
                this.applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    },

    applyTheme: function (theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this.updateIcon(theme);

        // Dispatch event for other components (like Charts) to update
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme } }));
    },

    toggle: function () {
        const current = document.documentElement.getAttribute('data-theme');
        const newTheme = current === 'dark' ? 'light' : 'dark';

        localStorage.setItem('theme', newTheme);
        this.applyTheme(newTheme);
    },

    updateChartColors: function (chart) {
        if (!chart) return;

        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const textColor = isDark ? '#e0e0e0' : '#666';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

        // Function to recursively update chart options
        const updateOptions = (obj) => {
            if (!obj) return;

            // Check specific color properties known in Chart.js
            if (obj.color && typeof obj.color === 'string') obj.color = textColor;
            if (obj.borderColor && typeof obj.borderColor === 'string' && obj.borderColor.includes('0.1')) obj.borderColor = gridColor; // Heuristic for grid lines

            // Specifically handling scales config
            if (obj.scales) {
                Object.values(obj.scales).forEach(scale => {
                    if (scale.ticks) scale.ticks.color = textColor;
                    if (scale.grid) scale.grid.color = gridColor;
                    if (scale.title) scale.title.color = textColor;
                });
            }

            // Specifically handling plugins
            if (obj.plugins) {
                if (obj.plugins.legend && obj.plugins.legend.labels) obj.plugins.legend.labels.color = textColor;
                if (obj.plugins.datalabels) obj.plugins.datalabels.color = isDark ? '#fff' : '#fff'; // Always white for bar labels usually
                if (obj.plugins.title) obj.plugins.title.color = textColor;
            }
        };

        // Simplified update for common Chart.js structures
        if (chart.options) {
            if (chart.options.scales) {
                Object.keys(chart.options.scales).forEach(key => {
                    const scale = chart.options.scales[key];
                    if (scale.ticks) scale.ticks.color = textColor;
                    if (scale.grid) scale.grid.color = gridColor;
                    if (scale.title) scale.title.color = textColor;
                });
            }
            if (chart.options.plugins) {
                if (chart.options.plugins.legend && chart.options.plugins.legend.labels) {
                    chart.options.plugins.legend.labels.color = textColor;
                }
                if (chart.options.plugins.title) {
                    chart.options.plugins.title.color = textColor;
                }
            }
        }

        chart.update();
    },

    updateIcon: function (theme) {
        const icon = document.getElementById('themeIcon');
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    },

    // Helper to inject toggle button into header
    renderButton: function (containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const btn = document.createElement('button');
        btn.className = 'theme-toggle-btn';
        btn.onclick = () => this.toggle();
        btn.title = 'Switch Theme';

        const icon = document.createElement('i');
        icon.id = 'themeIcon';
        // Set initial icon based on current state (might be null if just rendered)
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        icon.className = current === 'dark' ? 'fas fa-sun' : 'fas fa-moon';

        btn.appendChild(icon);
        container.appendChild(btn);
    }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    themeToggle.init();
});
