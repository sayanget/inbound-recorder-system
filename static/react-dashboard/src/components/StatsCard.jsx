import { memo } from 'react'

const StatsCard = memo(({ title, value, unit, icon, trend }) => {
    const getTrendIcon = () => {
        if (!trend) return null
        if (trend > 0) return '📈'
        if (trend < 0) return '📉'
        return '➡️'
    }

    const getTrendClass = () => {
        if (!trend) return ''
        return trend > 0 ? 'trend-up' : trend < 0 ? 'trend-down' : 'trend-neutral'
    }

    return (
        <div className="stats-card">
            <div className="stats-card-icon">{icon}</div>
            <div className="stats-card-content">
                <h3 className="stats-card-title">{title}</h3>
                <div className="stats-card-value">
                    <span className="value">{value}</span>
                    <span className="unit">{unit}</span>
                </div>
                {trend !== undefined && (
                    <div className={`stats-card-trend ${getTrendClass()}`}>
                        <span className="trend-icon">{getTrendIcon()}</span>
                        <span className="trend-value">{Math.abs(trend)}%</span>
                    </div>
                )}
            </div>
        </div>
    )
})

StatsCard.displayName = 'StatsCard'

export default StatsCard
