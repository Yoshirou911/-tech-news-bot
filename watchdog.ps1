$root = "C:\Users\yoshi\OneDrive\デスクトップ\情報収集"

$dashboardUp = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if (-not $dashboardUp) {
    Start-Process -FilePath "pythonw" -ArgumentList "dashboard.py" -WorkingDirectory $root -WindowStyle Hidden
}

$botUp = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -like "*discord_bot.py*" }
if (-not $botUp) {
    Start-Process -FilePath "pythonw" -ArgumentList "discord_bot.py" -WorkingDirectory $root -WindowStyle Hidden
}
