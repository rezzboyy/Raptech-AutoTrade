# Verifikasi rilis mandiri: jalankan EXE dari folder dist dengan PATH TERBATAS
# (tanpa Qt bin) untuk membuktikan semua DLL/plugin sudah terkumpul. Auto-kill.
#   powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\verify_dist.ps1
$dist = "C:\XaviqCppDist\XTradingEngine"
$env:PATH = "$dist;C:\Windows\System32;C:\Windows"
$env:QT_QPA_PLATFORM = "offscreen"
$p = Start-Process -FilePath "$dist\XTradingEngine.exe" -ArgumentList "--smoke" `
    -Wait -PassThru -NoNewWindow -RedirectStandardError "$dist\_err.txt"
Write-Host "DIST_EXIT=$($p.ExitCode)"
Get-Content "$dist\_err.txt" -ErrorAction SilentlyContinue
exit $p.ExitCode
