While(1) {
    Start-Process -FilePath "python.exe" -NoNewWindow -ArgumentList ".\solarstats.py","record-stats","--verbose"
    Start-Sleep -Seconds 90
}
