import { useState, useEffect, useCallback } from 'react'
import { fetchStatistics } from '../utils/api'

/**
 * Custom hook for fetching statistics data
 * Implements proper loading and error states
 * Uses useCallback to memoize refetch function
 */
export const useStatistics = (dateRange) => {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    const fetchData = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const result = await fetchStatistics(dateRange)
            setData(result)
        } catch (err) {
            setError(err)
            console.error('Failed to fetch statistics:', err)
        } finally {
            setLoading(false)
        }
    }, [dateRange])

    useEffect(() => {
        fetchData()
    }, [fetchData])

    // Memoized refetch function
    const refetch = useCallback(() => {
        fetchData()
    }, [fetchData])

    return { data, loading, error, refetch }
}
