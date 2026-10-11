@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PSModulePath="
for %%I in ("%CD%\..") do set "PRIVACYGUARD_PACKAGES=%%~fI"
if not exist logs mkdir logs
rem Windows PowerShell 5.1 needs UTF-8 BOM for non-ASCII script text.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '.' -Filter '*.ps1' | ForEach-Object { [IO.File]::WriteAllText($_.FullName, [IO.File]::ReadAllText($_.FullName, [Text.Encoding]::UTF8), (New-Object Text.UTF8Encoding($true))) }"
if errorlevel 1 goto failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\Check-Offline-Windows.ps1" -TargetDirectory "%CD%" -PackageDirectory "%PRIVACYGUARD_PACKAGES%" -InstallationGate
if errorlevel 1 goto failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\Install-Offline-Windows.ps1" -PackageDirectory "%PRIVACYGUARD_PACKAGES%" -InstallPython
if errorlevel 1 goto failed
echo Installation complete. Double-click Launch-PrivacyGuard.cmd to start.
if not defined PRIVACYGUARD_NONINTERACTIVE pause
exit /b 0
:failed
echo Installation failed. Preserve logs and consult docs\installation\faq.md.
if not defined PRIVACYGUARD_NONINTERACTIVE pause
exit /b 1
