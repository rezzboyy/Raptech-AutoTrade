# Smoke test QML offscreen: muat UI, cek rootObjects (exit 0). Auto-kill bila macet.
#   powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\smoke.ps1
$ErrorActionPreference = "Stop"
$root = "C:\XaviqCpp"
$env:PATH = "C:\Qt\6.8.1\mingw_64\bin;C:\Qt\Tools\mingw1310_64\bin;$env:PATH"
$env:QML2_IMPORT_PATH = "C:\Qt\6.8.1\mingw_64\qml"
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process -FilePath "$root\build\xaviq.exe" -ArgumentList "--smoke" `
    -Wait -PassThru -NoNewWindow -RedirectStandardError "$root\_smoke_err.txt"
Write-Host "SMOKE_EXIT=$($p.ExitCode)"
Get-Content "$root\_smoke_err.txt" -ErrorAction SilentlyContinue
exit $p.ExitCode
