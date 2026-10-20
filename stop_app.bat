@echo off
echo =======================================================
echo          Stopping Naughty or not (Sanction checK)      
echo =======================================================

echo Stopping Streamlit processes...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*streamlit run*' -or $_.Name -eq 'streamlit.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo Stopping Docker containers...
docker compose stop

echo Application stopped successfully.
