import { memo } from 'react'

const DashboardHeader = memo(({
    title,
    language,
    theme,
    onToggleTheme,
    onChangeLanguage,
    onRefresh,
    onDateChange
}) => {
    const languages = [
        { code: 'zh', label: '中文' },
        { code: 'en', label: 'English' },
        { code: 'es', label: 'Español' }
    ]

    return (
        <header className="dashboard-header">
            <div className="header-left">
                <h1>{title}</h1>
            </div>

            <div className="header-right">
                {/* Language Selector */}
                <div className="language-selector">
                    {languages.map(lang => (
                        <button
                            key={lang.code}
                            className={`lang-btn ${language === lang.code ? 'active' : ''}`}
                            onClick={() => onChangeLanguage(lang.code)}
                        >
                            {lang.label}
                        </button>
                    ))}
                </div>

                {/* Theme Toggle */}
                <button
                    className="theme-toggle"
                    onClick={onToggleTheme}
                    aria-label="Toggle theme"
                >
                    {theme === 'light' ? '🌙' : '☀️'}
                </button>

                {/* Refresh Button */}
                <button
                    className="refresh-btn"
                    onClick={onRefresh}
                    aria-label="Refresh data"
                >
                    🔄
                </button>
            </div>
        </header>
    )
})

DashboardHeader.displayName = 'DashboardHeader'

export default DashboardHeader
