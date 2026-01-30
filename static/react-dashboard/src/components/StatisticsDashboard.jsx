import { useState, useEffect, useMemo, useCallback } from 'react'
import DashboardHeader from './DashboardHeader'
import StatsCard from './StatsCard'
import ChartCard from './ChartCard'
import { useStatistics } from '../hooks/useStatistics'
import { formatNumber } from '../utils/formatters'

const calculateTypeAvg = (stats, type) => {
    if (!stats) return 0
    const item = stats.find(s => s.vehicle_type === type)
    if (!item || item.count === 0) return 0
    return (item.total_pieces / item.count).toFixed(0)
}

const StatisticsDashboard = ({ language, theme, onToggleTheme, onChangeLanguage }) => {
    const [dateRange, setDateRange] = useState({ start: null, end: null })

    // Custom hook for data fetching with loading and error states
    const { data, loading, error, refetch } = useStatistics(dateRange)

    // Memoized translations to avoid recreation on every render
    const t = useMemo(() => ({
        zh: {
            title: '入库统计仪表板',
            totalPieces: '总货量',
            totalVehicles: '总车次',
            totalPallets: '总托盘',
            nightShift: '夜班车次',
            nightShift: '夜班车次',
            avgPieces: '平均货量',
            avgPallets: '平均托盘',
            avg53: '53尺均货',
            avg26: '26尺均货',
            refresh: '刷新数据'
        },
        en: {
            title: 'Inbound Statistics Dashboard',
            totalPieces: 'Total Pieces',
            totalVehicles: 'Total Vehicles',
            totalPallets: 'Total Pallets',
            nightShift: 'Night Shift',
            avgPieces: 'Average Pieces',
            refresh: 'Refresh Data'
        },
        es: {
            title: 'Panel de Estadísticas',
            totalPieces: 'Total de Piezas',
            totalVehicles: 'Total de Vehículos',
            totalPallets: 'Total de Paletas',
            nightShift: 'Turno de Noche',
            avgPieces: 'Promedio de Piezas',
            refresh: 'Actualizar Datos'
        }
    }), [])

    // Memoized computed values
    const stats = useMemo(() => {
        if (!data) return null
        return {
            totalPieces: data.totalPieces || 0,
            totalVehicles: data.totalVehicles || 0,
            totalPallets: data.totalPallets || 0,
            nightShiftVehicles: data.nightShiftVehicles || 0,
            avgPieces: data.totalVehicles > 0
                ? (data.totalPieces / data.totalVehicles).toFixed(2)
                : 0,
            avgPallets: data.totalVehicles > 0
                ? (data.totalPallets / data.totalVehicles).toFixed(1)
                : 0,
            // Calculate specific averages
            avg53: calculateTypeAvg(data.rawVehicleStats, '53英尺'),
            avg26: calculateTypeAvg(data.rawVehicleStats, '26英尺')
        }
    }, [data])


    // Callback with useCallback to prevent unnecessary re-renders
    const handleRefresh = useCallback(() => {
        refetch()
    }, [refetch])

    const handleDateChange = useCallback((range) => {
        setDateRange(range)
    }, [])

    if (loading) {
        return <div className="loading">加载中...</div>
    }

    if (error) {
        return <div className="error">错误: {error.message}</div>
    }

    return (
        <div className="statistics-dashboard">
            <DashboardHeader
                title={t[language].title}
                language={language}
                theme={theme}
                onToggleTheme={onToggleTheme}
                onChangeLanguage={onChangeLanguage}
                onRefresh={handleRefresh}
                onDateChange={handleDateChange}
            />

            <div className="dashboard-content">
                {/* Stats Cards Grid */}
                <div className="stats-grid">
                    <StatsCard
                        title={t[language].totalPieces}
                        value={formatNumber(stats?.totalPieces)}
                        unit="件"
                        icon="📦"
                        trend={data?.piecesTrend}
                    />
                    <StatsCard
                        title={t[language].totalVehicles}
                        value={formatNumber(stats?.totalVehicles)}
                        unit="车"
                        icon="🚛"
                        trend={data?.vehiclesTrend}
                    />
                    <StatsCard
                        title={t[language].totalPallets}
                        value={formatNumber(stats?.totalPallets)}
                        unit="板"
                        icon="🧱"
                    />
                    <StatsCard
                        title={t[language].nightShift}
                        value={stats?.nightShiftVehicles}
                        unit="车"
                        icon="🌙"
                    />
                    <StatsCard
                        title={t[language].avgPallets}
                        value={stats?.avgPallets}
                        unit="板/车"
                        icon="📊"
                    />
                    <StatsCard
                        title={t[language].avgPieces}
                        value={stats?.avgPieces}
                        unit="件/车"
                        icon="📊"
                    />
                    <StatsCard
                        title={t[language].avg53}
                        value={stats?.avg53}
                        unit="件"
                        icon="🚛"
                    />
                    <StatsCard
                        title={t[language].avg26}
                        value={stats?.avg26}
                        unit="件"
                        icon="🚚"
                    />
                </div>

                {/* Charts Grid */}
                <div className="charts-grid">
                    <ChartCard
                        title="每日货量趋势"
                        type="line"
                        data={data?.dailyData}
                        language={language}
                    />
                    <ChartCard
                        title="周环比对比"
                        type="bar"
                        data={data?.weeklyData}
                        language={language}
                    />
                    <ChartCard
                        title="货物类型分布"
                        type="pie"
                        data={data?.categoryData}
                        language={language}
                    />
                </div>
            </div>
        </div>
    )
}

export default StatisticsDashboard
