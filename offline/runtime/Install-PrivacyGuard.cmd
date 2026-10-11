@echo off
chcp 65001 >nul
title PrivacyGuard 安装向导
cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"
echo [1/2] 正在执行安装前强制检查...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Check-Offline-Windows.ps1" -TargetDirectory "%~dp0." -PackageDirectory "%~dp0..\." -InstallationGate
if errorlevel 1 goto preflight_failed
echo [2/2] 预检通过，开始离线安装。
echo 正在安装 PrivacyGuard，请勿关闭窗口。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Offline-Windows.ps1" -InstallPython
if errorlevel 1 goto failed
echo.
echo 安装成功。现在可以双击 Launch-PrivacyGuard.cmd 启动。
if not defined PRIVACYGUARD_NONINTERACTIVE pause
exit /b 0
:preflight_failed
echo.
echo 安装前检查未通过，已停止安装。请根据上方 FAIL 项处理，FAQ 位于 docs\installation\faq.md。
if not defined PRIVACYGUARD_NONINTERACTIVE pause
exit /b 2
:failed
echo.
echo 安装失败。请保留本窗口内容和 logs 文件夹，再交给安装 Agent 排查。
if not defined PRIVACYGUARD_NONINTERACTIVE pause
exit /b 1
