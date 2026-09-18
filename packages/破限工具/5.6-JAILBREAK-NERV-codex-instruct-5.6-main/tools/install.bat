# @echo off
:: NERV-BREAK-5.6 Tool Installer
:: Download/install portable security tools for Windows
:: Run as Administrator recommended

echo.
echo   ========================================
echo     NERV-BREAK-5.6 Tool Installer
echo   ========================================
echo.
echo   This installs portable security tools into tools\win\
echo.
echo   1. Install ALL tools (recommended)
echo   2. Network tools (nmap, masscan)
echo   3. Web tools (sqlmap, dirb, ffuf, gobuster)
echo   4. Reverse tools (radare2, binwalk)
echo   5. Custom: Enter tool name
echo   6. Back
echo.
set /p "choice=  choice: "

if "%choice%"=="1" goto all
if "%choice%"=="2" goto network
if "%choice%"=="3" goto web
if "%choice%"=="4" goto reverse
if "%choice%"=="5" goto custom
if "%choice%"=="6" goto end

:all
call :network
call :web
call :reverse
echo All tools installed.
goto end

:network
echo Installing network tools...
where nmap >nul 2>&1 && echo   [OK] nmap already installed || echo   [--] nmap: https://nmap.org/download.html
echo   Use WSL Kali for masscan, tcpdump, netcat: wsl --install -d kali-linux
goto :eof

:web
echo Installing web tools...
echo   sqlmap: pip install sqlmap
pip install sqlmap 2>nul && echo   [OK] sqlmap installed || echo   [--] sqlmap failed (try: pip install sqlmap)
echo   dirb: included in Kali WSL
echo   ffuf: go install github.com/ffuf/ffuf@latest
echo   gobuster: go install github.com/OJ/gobuster/v3@latest
goto :eof

:reverse
echo Installing reverse tools...
echo   radare2: https://github.com/radareorg/radare2/releases
echo   binwalk: pip install binwalk
pip install binwalk 2>nul && echo   [OK] binwalk installed || echo   [--] binwalk failed
echo   Ghidra: https://github.com/NationalSecurityAgency/ghidra/releases
goto :eof

:custom
set /p "tool=  Tool name: "
echo Check: https://www.kali.org/tools/%tool%/
goto end

:end
echo.
echo   For full Kali Linux tools locally:
echo     wsl --install -d kali-linux
echo     wsl -d kali-linux
echo     sudo apt update && sudo apt install -y kali-linux-headless
echo.
pause
