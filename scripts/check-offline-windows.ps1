param(
    [string]$TargetDirectory = "D:\PrivacyGuard\v0.1.4",
    [double]$SpeedMbps = 0,
    [string]$PackageDirectory = "",
    [switch]$InstallationGate
)

$ErrorActionPreference = "SilentlyContinue"
$Failures = 0
$Warnings = 0
$DownloadGiB = 1.61
$WheelCount = 164
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $PackageDirectory) { $PackageDirectory = Split-Path -Parent $ScriptRoot }
function Ok($Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Warn($Message) { $script:Warnings++; Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail($Message) { $script:Failures++; Write-Host "[FAIL] $Message" -ForegroundColor Red }

Write-Host "PrivacyGuard standard offline preflight (Windows)"
Write-Host "Target: $TargetDirectory"
Write-Host "------------------------------------------------"

if ([Environment]::Is64BitOperatingSystem) { Ok "Architecture: Windows x64" } else { Fail "The v0.1.4 package requires Windows x64." }
$Os = Get-CimInstance Win32_OperatingSystem
if ($Os) {
    $Build = [int]$Os.BuildNumber
    if ($Build -ge 19045) { Ok "OS: $($Os.Caption), build $Build" } else { Fail "Windows 10 22H2 (build 19045) or Windows 11 is required; found build $Build." }
    $RamGb = [math]::Floor(($Os.TotalVisibleMemorySize * 1KB) / 1GB)
    if ($RamGb -ge 16) { Ok "Memory: ${RamGb} GB" } elseif ($RamGb -ge 8) { Warn "Memory: ${RamGb} GB; 16 GB is recommended and OCR may be slow." } else { Fail "Memory: ${RamGb} GB; at least 8 GB is required." }
} else { Fail "Unable to read Windows system information." }

$TargetRoot = [IO.Path]::GetPathRoot($TargetDirectory)
$DriveName = if ($TargetRoot) { $TargetRoot.Substring(0,1) } else { "" }
$Drive = if ($DriveName) { Get-PSDrive -Name $DriveName } else { $null }
if (-not $Drive) {
    Fail "Target drive $TargetRoot does not exist. Ask before switching to $env:USERPROFILE\Documents\PrivacyGuard\v0.1.4."
} else {
    $FreeGb = [math]::Floor($Drive.Free / 1GB)
    if ($FreeGb -ge 15) { Ok "Free disk on ${TargetRoot}: ${FreeGb} GB" } elseif ($FreeGb -ge 10) { Warn "Free disk on ${TargetRoot}: ${FreeGb} GB; 15 GB is recommended." } else { Fail "Free disk on ${TargetRoot}: ${FreeGb} GB; at least 10 GB is required." }
}

if ($PSVersionTable.PSVersion.Major -ge 5) { Ok "PowerShell: $($PSVersionTable.PSVersion)" } else { Fail "PowerShell 5.1 or newer is required." }
if (Get-Command tar.exe -ErrorAction SilentlyContinue) { Ok "Windows tar.exe is available" } else { Fail "tar.exe is required to unpack the model archives. Update Windows before installing." }

$VcRuntime = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
if ($VcRuntime -and $VcRuntime.Installed -eq 1) {
    Ok "Microsoft Visual C++ x64 Runtime: $($VcRuntime.Version)"
} else {
    if ($InstallationGate) { Fail "Microsoft Visual C++ 2015-2022 x64 Runtime is required. Install it only from https://aka.ms/vs/17/release/vc_redist.x64.exe." }
    else { Warn "Microsoft Visual C++ 2015-2022 x64 Runtime was not detected. Download only from https://aka.ms/vs/17/release/vc_redist.x64.exe and install it before PrivacyGuard." }
}

$Python = $null
try { $Python = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim() } catch {}
if ($Python) { Ok "Python 3.11 is already installed: $Python" } else { Warn "Python 3.11 is not installed; the runtime package includes prerequisites\python-3.11.9-amd64.exe." }

foreach ($Port in @(8000,8080,8082)) {
    $Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Listener) { Warn "Port $Port is already in use by PID $($Listener.OwningProcess)." } else { Ok "Port $Port is available" }
}

if ($InstallationGate) {
    Write-Host "------------------------------------------------"
    Write-Host "Installation gate: package integrity and write access"
    $VersionFile = Join-Path $ScriptRoot "OFFLINE_VERSION"
    if (-not (Test-Path $VersionFile)) { Fail "Missing OFFLINE_VERSION in $ScriptRoot" }
    else {
        $Version = (Get-Content $VersionFile -Raw).Trim()
        $ManifestPath = Join-Path $PackageDirectory "SHA256SUMS"
        if (-not (Test-Path $ManifestPath)) { Fail "Missing SHA256SUMS in $PackageDirectory" }
        else {
            $RequiredFiles = @(
                "PrivacyGuard-standard-windows-x64-runtime-$Version.zip",
                "PrivacyGuard-standard-model-has-$Version.tar.gz",
                "PrivacyGuard-standard-model-paddleocr-$Version.tar.gz"
            )
            $Manifest = Get-Content $ManifestPath
            foreach ($Name in $RequiredFiles) {
                $Path = Join-Path $PackageDirectory $Name
                if (-not (Test-Path $Path)) { Fail "Missing package: $Name"; continue }
                $Line = $Manifest | Where-Object { $_ -match "\s+$([regex]::Escape($Name))$" } | Select-Object -First 1
                if (-not $Line) { Fail "SHA256SUMS has no entry for $Name"; continue }
                $Expected = ($Line -split "\s+")[0].ToLowerInvariant()
                $Actual = (Get-FileHash -Algorithm SHA256 $Path).Hash.ToLowerInvariant()
                if ($Expected -eq $Actual) { Ok "SHA-256: $Name" } else { Fail "SHA-256 mismatch: $Name" }
            }
        }
    }
    try {
        New-Item -ItemType Directory -Force -Path $TargetDirectory | Out-Null
        $Probe = Join-Path $TargetDirectory ".privacyguard-write-test-$PID.tmp"
        [IO.File]::WriteAllText($Probe, "ok")
        Remove-Item $Probe -Force
        Ok "Installation directory is writable: $TargetDirectory"
    } catch { Fail "Installation directory is not writable: $TargetDirectory ($($_.Exception.Message))" }
}

Write-Host "------------------------------------------------"
Write-Host "Installation plan"
Write-Host "Files to download: 4 (Windows runtime, HaS model, PaddleOCR model, SHA256SUMS)"
Write-Host "Download size: about $DownloadGiB GiB; bundled Python wheels: $WheelCount"
if ($SpeedMbps -gt 0) {
    $DownloadMinutes = [math]::Ceiling(($DownloadGiB * 8192 / $SpeedMbps / 60) * 1.2)
    Write-Host "Estimated download at $SpeedMbps Mbps: about $DownloadMinutes minutes (includes 20% overhead)"
} else {
    Write-Host "Estimated download: 10 Mbps 27-35 min; 50 Mbps 6-10 min; 100 Mbps 3-6 min"
    Write-Host "Pass -SpeedMbps <number> for a machine-specific estimate."
}
if ($RamGb -ge 16) { Write-Host "Estimated install + first startup: 10-25 minutes" }
else { Write-Host "Estimated install + first startup: 20-45 minutes; avoid other memory-heavy apps" }
Write-Host "Expected disk after extraction: about 8-10 GB; keep 15 GB free for logs and documents."

Write-Host "------------------------------------------------"
Write-Host "Bundled: frontend, Python wheels, Python 3.11 installer, llama.cpp, HaS and PaddleOCR model packages."
Write-Host "Not required: Node.js, npm, Git, WSL, Docker, NVIDIA GPU, CUDA."
Write-Host "Result: $Failures failure(s), $Warnings warning(s)"
if ($Failures -gt 0) { exit 2 }
