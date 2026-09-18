@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0\.."
title NERV-BREAK-5.6

:menu
cls
echo.
echo   ============================================
echo          NERV-BREAK-5.6  Control Panel
echo   ============================================
echo.
echo   ── Proxy ──────────────────────────────────
echo   [1] start     Auto-detect + deploy + launch
echo   [2] stop      Kill proxy + restore Codex
echo   [3] status    Check proxy state
echo.
echo   ── Kali Linux ─────────────────────────────
echo   [4] kali-wsl  Install WSL Kali (recommended)
echo   [5] kali-docker  Setup Docker Kali
echo   [6] kali-ssh     Configure remote SSH Kali
echo.
echo   ── Tools ──────────────────────────────────
echo   [7] tools-check   Check installed tools
echo   [8] tools-install Install Python tools
echo.
echo   ── System ─────────────────────────────────
echo   [9] deploy    Deploy bridge.md + skills
echo   [0] quit      Exit
echo   ============================================
echo.
set /p "c=  choice: "

if "%c%"=="1" goto start
if "%c%"=="2" goto stop
if "%c%"=="3" goto status
if "%c%"=="4" goto kali_wsl
if "%c%"=="5" goto kali_docker
if "%c%"=="6" goto kali_ssh
if "%c%"=="7" goto tools_check
if "%c%"=="8" goto tools_install
if "%c%"=="9" goto deploy
if "%c%"=="0" goto quit
goto menu

:start
cls
echo   Starting NERV-BREAK-5.6...
start "nerv-proxy" /MIN python proxy_relay.py
timeout /t 3 /nobreak >nul
echo   Proxy: http://127.0.0.1:8080
echo   Panel: http://localhost:8090
echo   Restart Codex CLI and type: zxwn
pause
goto menu

:stop
cls
echo   Stopping proxy...
taskkill /FI "WINDOWTITLE eq nerv*" /F 2>nul
echo   Restoring Codex config...
python proxy_relay.py --restore 2>nul
echo   Done.
pause
goto menu

:status
cls
netstat -ano 2>nul | findstr ":8080" >nul && (
    echo   Proxy: RUNNING on :8080
    curl -s http://127.0.0.1:8080 2>nul
) || echo   Proxy: STOPPED
pause
goto menu

:kali_wsl
cls
echo   Installing WSL Kali Linux (~1GB)...
wsl --install -d kali-linux
echo   After WSL restarts, run: sudo apt update && sudo apt install -y kali-linux-headless
echo   Then: python mcp_server.py --wsl
pause
goto menu

:kali_docker
cls
echo   docker pull kalilinux/kali-rolling
echo   docker run -d --name kali-tools kalilinux/kali-rolling sleep infinity
echo   docker exec kali-tools apt update && apt install -y kali-linux-headless
echo   Then: python mcp_server.py --docker kali-tools
pause
goto menu

:kali_ssh
cls
set /p "ip=  Kali IP: "
echo   python mcp_server.py --kali root@%ip%
pause
goto menu

:tools_check
cls
echo   Checking available tools...
python tools\check_tools.py 2>nul || echo   check_tools.py not found. Install WSL Kali for full toolset.
pause
goto menu

:tools_install
cls
echo   Installing Python security tools...
pip install sqlmap 2>nul && echo   [OK] sqlmap
pip install pwntools 2>nul && echo   [OK] pwntools
echo   For full toolset (60+ tools): choose [4] kali-wsl
pause
goto menu

:deploy
cls
echo   Deploying bridge.md + skills to Codex...
python deploy.py apply 2>nul && echo   [OK] Deployed || echo   [FAIL] deploy.py error
pause
goto menu

:quit
endlocal
exit /b
