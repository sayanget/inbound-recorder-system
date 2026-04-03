# Inbound Recorder Service Watchdog
# This script ensures the monitoring service is always active and responsive.
# Recommended to run via Windows Task Scheduler every 1-5 minutes.

$MonitorUrl = "http://localhost:8081/status"
$StartupScript = "start_with_monitor.bat"
$LogFile = "watchdog.log"
$PSScriptPath = $MyInvocation.MyCommand.Path
$BaseDir = Split-Path $PSScriptPath

cd $BaseDir

Function Write-Log {
    Param([string]$Message)
    $TimeStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $FullMessage = "[$TimeStamp] [Watchdog] $Message"
    Write-Host $FullMessage
    $FullMessage | Out-File -FilePath $LogFile -Append
}

Try {
    Write-Log "Checking system health at $MonitorUrl..."
    $Response = Invoke-RestMethod -Uri $MonitorUrl -Method Get -TimeoutSec 10 -ErrorAction Stop
    
    if ($Response.status -eq "running") {
        Write-Log "System is healthy. App (PID: $($Response.pid)) is running."
    } else {
        Write-Log "System is active but app is $($Response.status). Monitor supervisor will handle this."
    }
} Catch {
    Write-Log "[CRITICAL] Monitor is unresponsive or unreachable. Initiating recovery..."
    
    # 1. Kill existing monitor/app processes to clear any hung states
    Write-Log "Terminating any hung Python processes..."
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
        $_.CommandLine -like "*app_monitor.py*" -or $_.CommandLine -like "*single_app.py*" 
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    # 2. Restart the system via the monitor script
    Write-Log "Starting system via $StartupScript..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c $StartupScript" -WindowStyle Hidden
    
    Write-Log "Recovery triggered. System should be back online shortly."
}
