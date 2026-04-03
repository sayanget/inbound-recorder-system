import { useState, useEffect } from 'react'
import StatisticsDashboard from './components/StatisticsDashboard'
import ShadcnDashboard from './components/ShadcnDashboard'

function App() {
    const [language, setLanguage] = useState('zh')
    const [theme, setTheme] = useState('light')

    // Load theme and language from localStorage
    useEffect(() => {
        const savedTheme = localStorage.getItem('theme') || 'light'
        const savedLang = localStorage.getItem('language') || 'zh'
        setTheme(savedTheme)
        setLanguage(savedLang)
        document.documentElement.setAttribute('data-theme', savedTheme)
    }, [])

    const toggleTheme = () => {
        const newTheme = theme === 'light' ? 'dark' : 'light'
        setTheme(newTheme)
        localStorage.setItem('theme', newTheme)
        document.documentElement.setAttribute('data-theme', newTheme)
    }

    const changeLanguage = (lang) => {
        setLanguage(lang)
        localStorage.setItem('language', lang)
    }


    console.log('App: Rendering...');

    // Simple routing check
    const path = window.location.pathname;
    if (path.includes('/shadcn')) {
        return <div className="app"><ShadcnDashboard /></div>;
    }

    return (
        <div className="app">
            <StatisticsDashboard
                language={language}
                theme={theme}
                onToggleTheme={toggleTheme}
                onChangeLanguage={changeLanguage}
            />
        </div>
    )
}

export default App
