# Exit 0 if watch_sqlite_sync_neon.py is already running, else 1.
# Called from start_with_monitor.bat (must not embed complex PS in .bat — breaks CMD parentheses parsing).
$p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*watch_sqlite_sync_neon.py*' }
if ($p) { exit 0 } else { exit 1 }
