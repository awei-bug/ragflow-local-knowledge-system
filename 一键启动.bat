@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0docker"

where docker.exe >nul 2>&1 || goto no_docker
docker.exe info >nul 2>&1 || goto docker_stopped

echo [START] Starting RAGFlow with the repository Docker Compose configuration...
docker.exe compose -f docker-compose.yml up -d
if errorlevel 1 goto failed

start "" "http://127.0.0.1:8088"
echo [OK] RAGFlow is starting at http://127.0.0.1:8088
echo The first start may take several minutes while images are downloaded.
pause
exit /b 0

:no_docker
echo [ERROR] Docker was not found. Install Docker Desktop and add it to PATH.
pause
exit /b 1

:docker_stopped
echo [ERROR] Docker Desktop is not running. Start it and retry.
pause
exit /b 1

:failed
echo [ERROR] Docker Compose startup failed. Review the output above.
pause
exit /b 1
