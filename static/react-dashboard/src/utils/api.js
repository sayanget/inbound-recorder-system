/**
 * API utility functions for fetching data from Flask backend
 */

const API_BASE = '/api'

/**
 * Fetch statistics data
 * @param {Object} dateRange - Optional date range filter
 * @returns {Promise<Object>} Statistics data
 */
export const fetchStatistics = async (dateRange) => {
    try {
        const params = new URLSearchParams()
        if (dateRange?.start) params.append('start', dateRange.start)
        if (dateRange?.end) params.append('end', dateRange.end)

        // Fetch multiple endpoints in parallel
        const [statsResponse, dailyTrendResponse] = await Promise.all([
            fetch(`${API_BASE}/stats${params.toString() ? '?' + params.toString() : ''}`),
            fetch(`${API_BASE}/daily_trend`)
        ])

        if (!statsResponse.ok) {
            throw new Error(`Stats API error! status: ${statsResponse.status}`)
        }

        const data = await statsResponse.json()
        const dailyTrendData = dailyTrendResponse.ok ? await dailyTrendResponse.json() : { dates: [], pieces: [] }

        // Calculate night shift total
        const nightShiftTotal = (data.vehicles_19_to_20 || 0) +
            (data.vehicles_20_to_21 || 0) +
            (data.vehicles_after_24 || 0)

        // Transform data to match component expectations
        return {
            totalPieces: data.total_pieces || 0,
            totalVehicles: data.total_vehicles || 0,
            totalPallets: data.total_pallets || 0,
            nightShiftVehicles: nightShiftTotal,

            piecesTrend: data.pieces_trend,
            vehiclesTrend: data.vehicles_trend,
            palletsTrend: data.pallets_trend,
            nightShiftTrend: data.night_shift_trend,

            // Map daily trend data for charts
            dailyData: {
                labels: dailyTrendData.dates || [],
                values: dailyTrendData.pieces || [],
                values2: dailyTrendData.vehicles || [] // Add vehicles data for secondary axis
            },

            // Map weekly comparison (placeholder if API missing)
            weeklyData: null,

            // Map category stats (Vehicle Types)
            categoryData: transformCategoryData(data.vehicle_stats),
            rawVehicleStats: data.vehicle_stats || []
        }
    } catch (error) {
        console.error('API Error:', error)
        throw error
    }
}

/**
 * Transform category stats for pie chart
 */
const transformCategoryData = (vehicleStats) => {
    if (!vehicleStats || !Array.isArray(vehicleStats)) return { labels: [], values: [] }

    return {
        labels: vehicleStats.map(item => item.vehicle_type),
        values: vehicleStats.map(item => item.count)
    }
}
