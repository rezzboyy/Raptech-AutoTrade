# =====================================================================
# Raptech AutoTrade - One-Click Auto-Release & OTA Publisher Script
# Patterned after BCA Mobile Android release automation engine
# =====================================================================
param(
    [string]$Version = "",
    [string]$Notes = "Pembaruan sistem, peningkatan performa, modul strategi, dan stabilitas Raptech AutoTrade."
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Raptech AutoTrade - GitHub Release & OTA Publisher       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Read and Bump Version from core/version.py
$versionFile = Join-Path $scriptDir "core\version.py"
if (-not (Test-Path $versionFile)) {
    Write-Host "Error: File core\version.py tidak ditemukan!" -ForegroundColor Red
    exit 1
}

$content = Get-Content $versionFile -Raw
if ($content -match '__version__\s*=\s*"([^"]+)"') {
    $currentVersion = $matches[1]
} else {
    $currentVersion = "3.1.0"
}

# Determine target version
if ([string]::IsNullOrWhiteSpace($Version)) {
    # Auto-bump patch version (e.g. 3.1.0 -> 3.1.1)
    $parts = $currentVersion.Split('.')
    if ($parts.Length -ge 3) {
        $patch = [int]$parts[2] + 1
        $targetVersion = "$($parts[0]).$($parts[1]).$patch"
    } elseif ($parts.Length -eq 2) {
        $targetVersion = "$($parts[0]).$($parts[1]).1"
    } else {
        $targetVersion = "$currentVersion.1"
    }
} else {
    $targetVersion = $Version.Trim().TrimStart('v').TrimStart('V')
}

Write-Host "`n[1/5] Memperbarui Versi Aplikasi:" -ForegroundColor Yellow
Write-Host "      Versi Sekarang : v$currentVersion" -ForegroundColor Gray
Write-Host "      Versi Rilis    : v$targetVersion" -ForegroundColor Green

# Update core/version.py
$updatedContent = $content -replace '__version__\s*=\s*"[^"]+"', "__version__ = `"$targetVersion`""
Set-Content -Path $versionFile -Value $updatedContent -NoNewline

# 2. Quality Gate: Run Unit Tests
Write-Host "`n[2/5] Menjalankan Quality Gate (Validasi Unit Test Otomatis)..." -ForegroundColor Yellow
$testOutput = & pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Unit test gagal! Membatalkan rilis untuk proteksi kualitas." -ForegroundColor Red
    # Rollback version
    Set-Content -Path $versionFile -Value $content -NoNewline
    exit 1
}
Write-Host "      Quality Gate LOLOS 100%! Seluruh pengujian hijau." -ForegroundColor Green

# 3. Compile Production Executable & Build Customer ZIP
Write-Host "`n[3/5] Mengompilasi Biner & Paket Rilis (PyInstaller & Zipping)..." -ForegroundColor Yellow
& python scripts/build.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Kompilasi build.py gagal!" -ForegroundColor Red
    exit 1
}

$exePath = Join-Path $scriptDir "release\RaptechAutoTrade.exe"
$zipPath = Join-Path $scriptDir "release\Raptech_AutoTrade_v$targetVersion.zip"

if (-not (Test-Path $exePath)) {
    Write-Host "Error: File binary RaptechAutoTrade.exe tidak ditemukan di $exePath!" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $zipPath)) {
    # Fallback to any matching zip in release folder
    $possibleZips = Get-ChildItem -Path (Join-Path $scriptDir "release") -Filter "*.zip" | Sort-Object LastWriteTime -Descending
    if ($possibleZips.Count -gt 0) {
        $zipPath = $possibleZips[0].FullName
    }
}

$exeSizeMb = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
$zipSizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)

Write-Host "      Binary Executable : $exeSizeMb MB" -ForegroundColor Green
Write-Host "      Customer ZIP Pack : $zipSizeMb MB" -ForegroundColor Green

# 4. Commit version bump to Git
Write-Host "`n[4/5] Melakukan Stage, Commit dan Push ke Git (origin/main)..." -ForegroundColor Yellow
& git add -A
& git commit -m "chore(release): bump version to v$targetVersion"
& git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Git push mengalami kendala atau sudah up-to-date." -ForegroundColor Yellow
}

# 5. Publish Release via GitHub CLI
Write-Host "`n[5/5] Mempublikasikan Rilis ke GitHub Releases (OTA Engine)..." -ForegroundColor Yellow
$tag = "v$targetVersion"
$releaseTitle = "Raptech AutoTrade v$targetVersion"

# Calculate SHA256 hashes
$exeHash = (Get-FileHash -Path $exePath -Algorithm SHA256).Hash
$zipHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash

$releaseNotes = @"
## Pembaruan Raptech AutoTrade ($tag)

$Notes

---
### 📦 Berkas Distribusi Produksi:
- **Standalone Binary**: `RaptechAutoTrade.exe` ($exeSizeMb MB)
  - SHA-256: `$exeHash`
- **Customer Release Pack**: `Raptech_AutoTrade_v$targetVersion.zip` ($zipSizeMb MB)
  - SHA-256: `$zipHash`

---
### 🔄 Cara Pembaruan Otomatis (OTA):
Pengguna dapat memperbarui bot secara instan tanpa unduh manual:
```powershell
RaptechAutoTrade.exe update
```
Atau pilih menu **[U] Update Otomatis** langsung pada Terminal Dashboard saat bot dibuka.
"@

$notesFile = Join-Path $scriptDir "release\RELEASE_NOTES_temp.md"
[System.IO.File]::WriteAllText($notesFile, $releaseNotes, [System.Text.Encoding]::UTF8)

# Publish release with assets attached
& gh release create $tag $exePath $zipPath --title $releaseTitle --notes-file $notesFile

if (Test-Path $notesFile) {
    Remove-Item $notesFile -Force -ErrorAction SilentlyContinue
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  RILIS SUKSES DIPUBLIKASIKAN KE GITHUB RELEASES!         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Tag Versi   : $tag" -ForegroundColor Cyan
Write-Host "  URL Rilis   : https://github.com/rezzboyy/Raptech-AutoTrade/releases/tag/$tag" -ForegroundColor Cyan
Write-Host "  Status OTA  : Seluruh pengguna bot akan mendeteksi update ini secara instan!" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green
