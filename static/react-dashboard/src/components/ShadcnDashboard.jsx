import React, { useEffect, useState } from 'react';
import { fetchStatistics } from '../utils/api';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function ShadcnDashboard() {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchStatistics()
            .then(data => {
                setStats(data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    if (loading) return <div className="flex items-center justify-center h-screen">Loading stats...</div>;
    if (!stats) return <div className="flex items-center justify-center h-screen">Error loading stats.</div>;

    // Helper for formatting
    const fmt = (n) => n ? n.toLocaleString() : '0';

    return (
        <div className="p-8 space-y-8 bg-background min-h-screen text-foreground">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Inbound Dashboard</h2>
                    <p className="text-muted-foreground">Overview of inbound statistics (Shadcn UI Edition)</p>
                </div>
                <div className="flex items-center space-x-2">
                    <Button onClick={() => window.location.reload()}>Refresh</Button>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Pieces</CardTitle>
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            className="h-4 w-4 text-muted-foreground"
                        >
                            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                        </svg>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{fmt(stats.totalPieces)}</div>
                        <p className={`text-xs ${stats.piecesTrend > 0 ? 'text-red-500' : stats.piecesTrend < 0 ? 'text-green-500' : 'text-muted-foreground'}`}>
                            {stats.piecesTrend > 0 ? '+' : ''}{stats.piecesTrend}% from yesterday
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Vehicles</CardTitle>
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            className="h-4 w-4 text-muted-foreground"
                        >
                            <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
                        </svg>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{fmt(stats.totalVehicles)}</div>
                        <p className={`text-xs ${stats.vehiclesTrend > 0 ? 'text-red-500' : stats.vehiclesTrend < 0 ? 'text-green-500' : 'text-muted-foreground'}`}>
                            {stats.vehiclesTrend > 0 ? '+' : ''}{stats.vehiclesTrend}% from yesterday
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Pallets</CardTitle>
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            className="h-4 w-4 text-muted-foreground"
                        >
                            <rect width="20" height="14" x="2" y="5" rx="2" />
                            <path d="M2 10h20" />
                        </svg>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{fmt(stats.totalPallets)}</div>
                        <p className={`text-xs ${stats.palletsTrend > 0 ? 'text-red-500' : stats.palletsTrend < 0 ? 'text-green-500' : 'text-muted-foreground'}`}>
                            {stats.palletsTrend > 0 ? '+' : ''}{stats.palletsTrend}% from yesterday
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Night Shift</CardTitle>
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            className="h-4 w-4 text-muted-foreground"
                        >
                            <path d="M22 17v1c0 .5-.5 1-1 1H3c-.5 0-1-.5-1-1v-1" />
                        </svg>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{fmt(stats.nightShiftVehicles)}</div>
                        <p className={`text-xs ${stats.nightShiftTrend > 0 ? 'text-red-500' : stats.nightShiftTrend < 0 ? 'text-green-500' : 'text-muted-foreground'}`}>
                            {stats.nightShiftTrend > 0 ? '+' : ''}{stats.nightShiftTrend}% from yesterday
                        </p>
                    </CardContent>
                </Card>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Daily Trend</CardTitle>
                    </CardHeader>
                    <CardContent className="pl-2">
                        {/* Placeholder for chart */}
                        <div className="h-[200px] flex items-center justify-center text-muted-foreground">
                            Chart Component Here
                        </div>
                    </CardContent>
                </Card>
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Vehicle Types</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-8">
                            {/* List of vehicle types */}
                            {stats.rawVehicleStats && stats.rawVehicleStats.map((s, i) => (
                                <div className="flex items-center" key={i}>
                                    <div className="ml-4 space-y-1">
                                        <p className="text-sm font-medium leading-none">{s.vehicle_type || s[0]}</p>
                                        <p className="text-sm text-muted-foreground">{s.total_pieces || s[2]} Pieces</p>
                                    </div>
                                    <div className="ml-auto font-medium">+{s.count || s[1]}</div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
