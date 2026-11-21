# =====================================================================
# X Trading Engine - One-Click Auto-Release & OTA Publisher Script
# Patterned after BCA Mobile Android release automation engine
# =====================================================================
param(
    [string]$Version = "",
    [string]$Notes = "Pembaruan arsitektur Native C++ Qt 6.8.1, antarmuka workstation dark cyber-trading, installer Inno Setup Windows, dan sistem auto-update OTA mandiri."
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  X Trading Engine - GitHub Release & OTA Engine          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Read and Bump Version from py_backend/src/version.py
$pyVersionFile = Join-Path $scriptDir "py_backend\src\version.py"
$cppVersionFile = Join-Path $scriptDir "cpp\src\core\Version.h"
$cmakeFile = Join-Path $scriptDir "cpp\CMakeLists.txt"
$rcFile = Join-Path $scriptDir "cpp\app.rc"
$issFile = Join-Path $scriptDir "installer.iss"

if (-not (Test-Path $pyVersionFile)) {
    Write-Host "Error: File py_backend\src\version.py tidak ditemukan!" -ForegroundColor Red
    exit 1
}

$pyContent = Get-Content $pyVersionFile -Raw
if ($pyContent -match '__version__\s*=\s*"([^"]+)"') {
    $currentVersion = $matches[1]
} else {
    $currentVersion = "3.2.0"
}

# Determine target version
if ([string]::IsNullOrWhiteSpace($Version)) {
    # Check if current version has already been released on GitHub
    $tagCheck = & git ls-remote --tags origin "refs/tags/v$currentVersion" 2>$null
    if (-not $tagCheck) {
        $targetVersion = $currentVersion
    } else {
        # Auto-bump patch version (e.g. 3.2.0 -> 3.2.1)
        $parts = $currentVersion.Split('.')
        if ($parts.Length -ge 3) {
            $patch = [int]$parts[2] + 1
            $targetVersion = "$($parts[0]).$($parts[1]).$patch"
        } elseif ($parts.Length -eq 2) {
            $targetVersion = "$($parts[0]).$($parts[1]).1"
        } else {
            $targetVersion = "$currentVersion.1"
        }
    }
} else {
    $targetVersion = $Version.Trim().TrimStart('v').TrimStart('V')
}

$rcVersion = $targetVersion.Replace('.', ',')

Write-Host "`n[1/5] Memperbarui Versi Aplikasi:" -ForegroundColor Yellow
Write-Host "      Versi Sekarang : v$currentVersion" -ForegroundColor Gray
Write-Host "      Versi Rilis    : v$targetVersion" -ForegroundColor Green

# Simpan cadangan untuk rollback jika test gagal
$bakPy = $pyContent
$bakCpp = if (Test-Path $cppVersionFile) { Get-Content $cppVersionFile -Raw } else { "" }
$bakCmake = if (Test-Path $cmakeFile) { Get-Content $cmakeFile -Raw } else { "" }
$bakRc = if (Test-Path $rcFile) { Get-Content $rcFile -Raw } else { "" }
$bakIss = if (Test-Path $issFile) { Get-Content $issFile -Raw } else { "" }

# Update py_backend/src/version.py
$updatedPy = $pyContent -replace '__version__\s*=\s*"[^"]+"', "__version__ = `"$targetVersion`""
Set-Content -Path $pyVersionFile -Value $updatedPy -NoNewline

# Update cpp/src/core/Version.h
if (Test-Path $cppVersionFile) {
    $cppContent = Get-Content $cppVersionFile -Raw
    $updatedCpp = $cppContent -replace 'APP_VERSION\s*=\s*QStringLiteral\("[^"]+"\)', "APP_VERSION = QStringLiteral(`"$targetVersion`")"
    Set-Content -Path $cppVersionFile -Value $updatedCpp -NoNewline
}

# Update cpp/CMakeLists.txt
if (Test-Path $cmakeFile) {
    $cmakeContent = Get-Content $cmakeFile -Raw
    $updatedCmake = $cmakeContent -replace 'project\(XaviqTradingEngine VERSION [^\s]+ LANGUAGES CXX\)', "project(XaviqTradingEngine VERSION $targetVersion LANGUAGES CXX)"
    Set-Content -Path $cmakeFile -Value $updatedCmake -NoNewline
}

# Update cpp/app.rc
if (Test-Path $rcFile) {
    $rcContent = Get-Content $rcFile -Raw
    $updatedRc = $rcContent -replace 'FILEVERSION\s+[\d,]+', "FILEVERSION     $rcVersion,0"
    $updatedRc = $updatedRc -replace 'PRODUCTVERSION\s+[\d,]+', "PRODUCTVERSION  $rcVersion,0"
    $updatedRc = $updatedRc -replace 'VALUE "FileVersion",\s+"[^"]+"', "VALUE `"FileVersion`",      `"$targetVersion.0\0`""
    $updatedRc = $updatedRc -replace 'VALUE "ProductVersion",\s+"[^"]+"', "VALUE `"ProductVersion`",   `"$targetVersion\0`""
    Set-Content -Path $rcFile -Value $updatedRc -NoNewline
}

# Update installer.iss
if (Test-Path $issFile) {
    $issContent = Get-Content $issFile -Raw
    $updatedIss = $issContent -replace '#define\s+MyAppVersion\s+"[^"]+"', "#define MyAppVersion `"$targetVersion`""
    Set-Content -Path $issFile -Value $updatedIss -NoNewline
}

# 2. Quality Gate: Run Python & C++ Unit Tests
Write-Host "`n[2/5] Menjalankan Quality Gate (Validasi Unit Test Otomatis)..." -ForegroundColor Yellow

# Pastikan junction C:\XaviqCpp selalu valid
$JUNC = "C:\XaviqCpp"
if (Test-Path $JUNC) {
    $targetPath = (Get-Item $JUNC).Target
    if (-not $targetPath -or $targetPath -ne "$scriptDir\cpp") {
        rmdir $JUNC -Force >$null 2>&1
        cmd /c mklink /J "$JUNC" "$scriptDir\cpp" >$null 2>&1
    }
} else {
    cmd /c mklink /J "$JUNC" "$scriptDir\cpp" >$null 2>&1
}

# 2a. Python Unit Tests (pytest)
Write-Host "      --> Menjalankan 290 Unit Test Python Backend..." -ForegroundColor Gray
$env:PYTHONPATH = "$scriptDir\py_backend"
$pyTestOutput = & pytest "$scriptDir\py_backend\tests" -q 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Unit test Python gagal!" -ForegroundColor Red
    Write-Host $pyTestOutput -ForegroundColor Red
    # Rollback
    Set-Content -Path $pyVersionFile -Value $bakPy -NoNewline
    if ($bakCpp) { Set-Content -Path $cppVersionFile -Value $bakCpp -NoNewline }
    if ($bakCmake) { Set-Content -Path $cmakeFile -Value $bakCmake -NoNewline }
    if ($bakRc) { Set-Content -Path $rcFile -Value $bakRc -NoNewline }
    if ($bakIss) { Set-Content -Path $issFile -Value $bakIss -NoNewline }
    exit 1
}

# 2b. C++ QtTest Suite (CTest)
Write-Host "      --> Mengompilasi dan Menjalankan Test Suite C++..." -ForegroundColor Gray
& powershell -ExecutionPolicy Bypass -File "$JUNC\build.ps1" >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Kompilasi build C++ gagal!" -ForegroundColor Red
    exit 1
}

& powershell -ExecutionPolicy Bypass -File "$JUNC\runtests.ps1" >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Test suite C++ gagal!" -ForegroundColor Red
    exit 1
}

# 2c. C++ Smoke UI Test
& powershell -ExecutionPolicy Bypass -File "$JUNC\smoke.ps1" >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Smoke UI test gagal!" -ForegroundColor Red
    exit 1
}

Write-Host "      Quality Gate LOLOS 100%! Seluruh pengujian C++ & Python hijau." -ForegroundColor Green

# 3. Compile Production Executable & Build Distribution Package
Write-Host "`n[3/5] Mengompilasi Biner & Paket Distribusi Standalone..." -ForegroundColor Yellow
& powershell -ExecutionPolicy Bypass -File "$JUNC\deploy.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Eksekusi deploy.ps1 gagal!" -ForegroundColor Red
    exit 1
}

$localDist = "$scriptDir\dist\XTradingEngine"
$exePath = "$localDist\XTradingEngine.exe"
$zipPath = "$scriptDir\dist\XTradingEngine_Portable_v$targetVersion.zip"

if (-not (Test-Path $exePath)) {
    Write-Host "Error: File binary XTradingEngine.exe tidak ditemukan di $exePath!" -ForegroundColor Red
    exit 1
}

# Salin ZIP rilis ber-versi
$baseZip = "$scriptDir\dist\XTradingEngine.zip"
if (Test-Path $baseZip) {
    Copy-Item $baseZip $zipPath -Force
} else {
    Write-Host "      Mengompresi $zipPath..." -ForegroundColor Gray
    & tar -a -cf "$zipPath" -C "$localDist" .
}

# Kompilasi Inno Setup Installer
Write-Host "      Mengompilasi Installer Windows Resmi via Inno Setup 6..." -ForegroundColor Gray
$installerPs = Join-Path $scriptDir "build_installer.ps1"
if (Test-Path $installerPs) {
    & powershell -ExecutionPolicy Bypass -File "$installerPs" >$null 2>&1
}
$setupPath = "$scriptDir\dist\XTradingEngine_Setup_v$targetVersion.exe"

$exeSizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
$zipSizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
$setupSizeMb = if (Test-Path $setupPath) { [math]::Round((Get-Item $setupPath).Length / 1MB, 2) } else { 0 }

Write-Host "      Binary Executable : $exeSizeMb MB" -ForegroundColor Green
Write-Host "      Portable ZIP Pack : $zipSizeMb MB" -ForegroundColor Green
if (Test-Path $setupPath) {
    Write-Host "      Windows Installer : $setupSizeMb MB (Setup Wizard)" -ForegroundColor Green
}

# 4. Commit and Push to Git & GitHub
Write-Host "`n[4/5] Melakukan Stage, Commit dan Push ke GitHub..." -ForegroundColor Yellow

$repoOwner = "rezzboyy"
$repoName = "Raptech-AutoTrade"
$repoFull = "$repoOwner/$repoName"
$remoteUrl = "https://github.com/$repoFull.git"

# Periksa / Tambahkan Git Remote
$currentRemote = git remote get-url origin 2>$null
if (-not $currentRemote) {
    git remote add origin $remoteUrl
} elseif ($currentRemote -ne $remoteUrl) {
    git remote set-url origin $remoteUrl
}

# Stage, Commit, & Push
& git add -A
& git commit -m "chore(release): bump version to v$targetVersion"
& git push origin master
& git push origin master:main --force

# 5. Publish Release via GitHub CLI
Write-Host "`n[5/5] Mempublikasikan Rilis ke GitHub Releases (OTA Engine)..." -ForegroundColor Yellow
$tag = "v$targetVersion"
$releaseTitle = "X Trading Engine v$targetVersion"

# Calculate SHA256 hashes
$exeHash = (Get-FileHash -Path $exePath -Algorithm SHA256).Hash
$zipHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash
$setupHash = if (Test-Path $setupPath) { (Get-FileHash -Path $setupPath -Algorithm SHA256).Hash } else { "" }

$releaseNotes = @"
## Pembaruan X Trading Engine ($tag)

$Notes

---
### 📦 Berkas Distribusi Produksi:
- **Windows Setup Wizard (Inno Setup)**: `XTradingEngine_Setup_v$targetVersion.exe` ($setupSizeMb MB)
  - SHA-256: $setupHash
- **Portable ZIP Package**: `XTradingEngine_Portable_v$targetVersion.zip` ($zipSizeMb MB)
  - SHA-256: $zipHash
- **Standalone Binary**: `XTradingEngine.exe` ($exeSizeMb MB)
  - SHA-256: $exeHash

---
### 🔄 Cara Instalasi & Pembaruan Otomatis (OTA):
1. **Instalasi Bersih (Direkomendasikan)**:
   - Unduh dan jalankan installer resmi `XTradingEngine_Setup_v$targetVersion.exe`.
   - Setup Wizard akan membuat shortcut di Desktop dan Start Menu secara otomatis.
2. **Pembaruan Otomatis (In-App OTA - Tanpa Perlu Install Ulang)**:
   - Pengguna yang sudah memasang aplikasi cukup membukanya, dialog **Pembaruan Aplikasi Tersedia** akan otomatis muncul.
   - Atau klik tombol **Update v$targetVersion** pada status bar aplikasi untuk memperbarui dalam 1-klik tanpa uninstall atau pasang ulang!
3. **Versi Portabel Tanpa Instalasi**:
   - Ekstrak berkas `XTradingEngine_Portable_v$targetVersion.zip` dan jalankan `XTradingEngine.exe` atau `Run_XTradingEngine.bat`.
"@

$notesFile = Join-Path $scriptDir "RELEASE_NOTES_temp.md"
[System.IO.File]::WriteAllText($notesFile, $releaseNotes, [System.Text.Encoding]::UTF8)

# Publish release with assets attached
$assetsToUpload = @()
if (Test-Path $setupPath) { $assetsToUpload += $setupPath }
if (Test-Path $zipPath) { $assetsToUpload += $zipPath }
if (Test-Path $exePath) { $assetsToUpload += $exePath }

& gh release create $tag @assetsToUpload --title $releaseTitle --notes-file $notesFile

if (Test-Path $notesFile) {
    Remove-Item $notesFile -Force -ErrorAction SilentlyContinue
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  RILIS SUKSES DIPUBLIKASIKAN KE GITHUB RELEASES!         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Tag Versi   : $tag" -ForegroundColor Cyan
Write-Host "  URL Rilis   : https://github.com/$repoFull/releases/tag/$tag" -ForegroundColor Cyan
Write-Host "  Status OTA  : Seluruh pengguna akan otomatis mendeteksi update ini di aplikasi!" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green
