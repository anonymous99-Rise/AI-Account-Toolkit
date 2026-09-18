@echo off
:: NERV-BREAK-5.6 Kali Integration Setup
:: Run as Administrator on Windows

echo.
echo   ========================================
echo     NERV-BREAK-5.6 Kali Linux Setup
echo   ========================================
echo.
echo   1. Kali WSL       Install Kali via WSL (Windows Subsystem for Linux)
echo   2. Kali Docker     Run Kali tools via Docker
echo   3. Kali Remote     Connect to existing Kali VM via SSH
echo   4. Test            Verify connection
echo   5. Back            Exit
echo.
set /p "choice=  choice: "

if "%choice%"=="1" goto wsl
if "%choice%"=="2" goto docker
if "%choice%"=="3" goto remote
if "%choice%"=="4" goto test
if "%choice%"=="5" goto end

:wsl
echo.
echo Installing Kali Linux via WSL...
wsl --install -d kali-linux
echo.
echo After install, run these in Kali:
echo   sudo apt update && sudo apt install -y kali-linux-headless
echo   sudo apt install -y nmap sqlmap hydra metasploit-framework john hashcat
echo   sudo apt install -y radare2 binwalk exiftool foremost tcpdump netcat
echo   sudo apt install -y dirb nikto wpscan ffuf searchsploit
goto end

:docker
echo.
echo Starting Kali Docker...
docker pull kalilinux/kali-rolling
docker run -d --name kali-tools kalilinux/kali-rolling sleep infinity
docker exec kali-tools apt update
docker exec kali-tools apt install -y kali-linux-headless
echo.
echo Kali Docker ready. Tools in container.
echo Use: docker exec kali-tools [command]
goto end

:remote
echo.
set /p "ssh_host=  Kali SSH (user@host): "
set /p "ssh_port=  SSH port (default 22): "
if "%ssh_port%"=="" set ssh_port=22
echo Testing SSH connection...
ssh -o StrictHostKeyChecking=no -p %ssh_port% %ssh_host% "echo OK"
if errorlevel 1 (
    echo SSH failed. Check host/port/key.
) else (
    echo SSH OK. Start proxy with:
    echo   python mcp_server.py --kali %ssh_host%
)
goto end

:test
echo.
echo Testing tool availability...
where nmap >nul 2>&1 && echo   [OK] nmap || echo   [--] nmap (not found)
where sqlmap >nul 2>&1 && echo   [OK] sqlmap || echo   [--] sqlmap
where msfconsole >nul 2>&1 && echo   [OK] msfconsole || echo   [--] msfconsole
where hydra >nul 2>&1 && echo   [OK] hydra || echo   [--] hydra
wsl nmap --version >nul 2>&1 && echo   [OK] Kali WSL nmap || echo   [--] Kali WSL
docker exec kali-tools nmap --version >nul 2>&1 && echo   [OK] Kali Docker nmap || echo   [--] Kali Docker
echo.
goto end

:end
echo.
pause
