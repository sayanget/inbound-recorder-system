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

    // Default Sorting Schedule
    const defaults = {
        manual: { capacity: 3000, hoursPerShift: 9, schedule: [0, 0, 0, 0, 0, 0, 0] },
        machine: { capacity: 4500, hoursPerShift: 9, schedule: [0, 0, 0, 0, 0, 0, 0] },
        night: { capacity: 4500, hoursPerShift: 9, schedule: [0, 0, 0, 0, 0, 0, 0] }
    }

    // Helper to safely get nested values
    const getVal = (obj, p1, p2, def) => {
        try {
            return (obj && obj[p1] && obj[p1][p2] !== undefined) ? obj[p1][p2] : def
        } catch (e) {
            return def
        }
    }

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

    const [sortingSchedule, setSortingSchedule] = useState(null)

    useEffect(() => {
        const fetchSchedule = async () => {
            try {
                const response = await fetch('/api/sorting-schedule?t=' + new Date().getTime())
                if (response.ok) {
                    const data = await response.json()
                    setSortingSchedule(data)
                } else if (response.status === 401) {
                    console.warn('Not logged in, using default schedule')
                    setSortingSchedule(null)
                } else {
                    console.error('Failed to fetch sorting schedule:', response.status)
                    setSortingSchedule(null)
                }
            } catch (error) {
                console.error('Error fetching sorting schedule:', error)
                setSortingSchedule(null)
            }
        }
        fetchSchedule()
    }, [])

    // Memoized computed values
    const stats = useMemo(() => {
        if (!data) return null

        // Calculate estimated duration if schedule exists
        let estimatedDuration = 0
        let estimatedCompletionTime = null

        if (data.totalPieces > 0) {
            const dayMap = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
            const today = new Date().getDay()
            const dayIndex = today === 0 ? 6 : today - 1 // Mon=0, ... Sun=6

            const defaults = {
                manual: { capacity: 3000, schedule: [5, 5, 5, 4, 4, 4, 1], startTimes: [17, 17, 17, 17, 17, 17, 17] },
                machine: { capacity: 4500, schedule: [4, 4, 4, 4, 4, 2, 2] },
                night: { capacity: 4500, schedule: [0, 0, 0, 0, 0, 0, 0] }
            }

            // Use saved schedule or defaults
            const config = sortingSchedule ? {
                manual: sortingSchedule.manual || defaults.manual,
                machine: sortingSchedule.machine || defaults.machine,
                night: sortingSchedule.night || defaults.night
            } : defaults

            const manualCount = config.manual.schedule[dayIndex] || 0
            const machineCount = config.machine.schedule[dayIndex] || 0
            const nightCount = config.night.schedule[dayIndex] || 0

            const totalHourlyCapacity =
                (manualCount * config.manual.capacity) +
                (machineCount * config.machine.capacity) +
                (nightCount * config.night.capacity)


            if (totalHourlyCapacity > 0) {
                // Determine if we are "In Progress"
                // Get configured start time for today (default 17)
                const startTimeHour = (config.manual.startTimes && config.manual.startTimes[dayIndex] !== undefined)
                    ? config.manual.startTimes[dayIndex]
                    : 17

                const now = new Date()
                const startTime = new Date(now)
                startTime.setHours(startTimeHour, 0, 0, 0)

                const isAfterStart = now >= startTime

                if (isAfterStart) {
                    // Real-time calculation based on elapsed time and capacity
                    const elapsedMs = now.getTime() - startTime.getTime()
                    const elapsedHours = elapsedMs / (1000 * 60 * 60)
                    const processedPieces = Math.floor(elapsedHours * totalHourlyCapacity)
                    const remainingPieces = Math.max(0, data.totalPieces - processedPieces)

                    // Duration to clear REMAINING pieces
                    estimatedDuration = (remainingPieces / totalHourlyCapacity).toFixed(1)

                    // Completion Time = Now + Remaining Duration
                    const completionTime = new Date(now.getTime() + parseFloat(estimatedDuration) * 60 * 60 * 1000)

                    const m = (completionTime.getMonth() + 1).toString().padStart(2, '0')
                    const d = completionTime.getDate().toString().padStart(2, '0')
                    const h = completionTime.getHours().toString().padStart(2, '0')
                    const min = completionTime.getMinutes().toString().padStart(2, '0')
                    estimatedCompletionTime = `${m}-${d} ${h}:${min}`

                } else {
                    // Pre-start calculation based on total pieces
                    estimatedDuration = (data.totalPieces / totalHourlyCapacity).toFixed(1)

                    // Completion Time = Start Time (17:00) + Total Duration
                    const completionTime = new Date(startTime.getTime() + parseFloat(estimatedDuration) * 60 * 60 * 1000)

                    const m = (completionTime.getMonth() + 1).toString().padStart(2, '0')
                    const d = completionTime.getDate().toString().padStart(2, '0')
                    const h = completionTime.getHours().toString().padStart(2, '0')
                    const min = completionTime.getMinutes().toString().padStart(2, '0')
                    estimatedCompletionTime = `${m}-${d} ${h}:${min}`
                }
            }
        }

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
            avg26: calculateTypeAvg(data.rawVehicleStats, '26英尺'),
            estimatedDuration,
            estimatedCompletionTime
        }
    }, [data, sortingSchedule])


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
                    <StatsCard
                        title={language === 'zh' ? '预计完成时间' : 'Est. Completion'}
                        value={stats?.estimatedCompletionTime || '--:--'}
                        subtext={stats?.estimatedDuration ? (language === 'zh' ? `预计时长: ${stats.estimatedDuration} 小时` : `Duration: ${stats.estimatedDuration} Hours`) : null}
                        unit=""
                        icon="⏳"
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
