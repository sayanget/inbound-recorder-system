import { memo, useMemo } from 'react'
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    ArcElement,
    Title,
    Tooltip,
    Legend
} from 'chart.js'
import { Line, Bar, Pie } from 'react-chartjs-2'

// Register Chart.js components
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    ArcElement,
    Title,
    Tooltip,
    Legend
)

const ChartCard = memo(({ title, type, data, language }) => {
    const isDualAxis = type === 'line' && data?.values2?.length > 0

    // Memoize chart options to prevent recreation
    const options = useMemo(() => ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            },
            title: {
                display: false,
            },
            tooltip: {
                mode: 'index',
                intersect: false,
            },
        },
        ...(type !== 'pie' && {
            scales: isDualAxis ? {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    title: { display: true, text: '货量 (件)' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    beginAtZero: true,
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: '车次 (车)' }
                }
            } : {
                y: {
                    beginAtZero: true,
                },
            },
        }),
    }), [type, isDualAxis])

    // Memoize chart data transformation
    const chartData = useMemo(() => {
        if (!data) return null

        switch (type) {
            case 'line':
                const datasets = [{
                    label: '货量',
                    data: data.values || [],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.3,
                    yAxisID: isDualAxis ? 'y' : 'y',
                }]

                if (data.values2) {
                    datasets.push({
                        label: '车次',
                        data: data.values2,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.3,
                        yAxisID: 'y1',
                    })
                }

                return {
                    labels: data.labels || [],
                    datasets
                }

            case 'bar':
                return {
                    labels: data.labels || [],
                    datasets: data.datasets || []
                }

            case 'pie':
                return {
                    labels: data.labels || [],
                    datasets: [{
                        data: data.values || [],
                        backgroundColor: [
                            'rgba(255, 99, 132, 0.8)',
                            'rgba(54, 162, 235, 0.8)',
                            'rgba(255, 206, 86, 0.8)',
                            'rgba(75, 192, 192, 0.8)',
                            'rgba(153, 102, 255, 0.8)',
                            'rgba(255, 159, 64, 0.8)',
                            'rgba(201, 203, 207, 0.8)',
                            'rgba(75, 12, 192, 0.8)',
                            'rgba(0, 128, 0, 0.8)',
                            'rgba(128, 0, 128, 0.8)',
                        ],
                    }]
                }

            default:
                return null
        }
    }, [data, type, isDualAxis])

    const renderChart = () => {
        if (!chartData) return <div className="no-data">暂无数据</div>

        switch (type) {
            case 'line':
                return <Line options={options} data={chartData} />
            case 'bar':
                return <Bar options={options} data={chartData} />
            case 'pie':
                return <Pie options={options} data={chartData} />
            default:
                return null
        }
    }

    return (
        <div className="chart-card">
            <h3 className="chart-card-title">{title}</h3>
            <div className="chart-card-content">
                {renderChart()}
            </div>
        </div>
    )
})

ChartCard.displayName = 'ChartCard'

export default ChartCard
