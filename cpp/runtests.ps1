# Jalankan test unit C++ (ctest) untuk XAVIQ core.
# PENTING: lewat junction tanpa spasi (C:\XaviqCpp).
#   powershell -ExecutionPolicy Bypass -File C:\XaviqCpp\runtests.ps1
$ErrorActionPreference = "Stop"
$root = "C:\XaviqCpp"

$env:PATH = "C:\Qt\6.8.1\mingw_64\bin;C:\Qt\Tools\mingw1310_64\bin;C:\Qt\Tools\CMake_64\bin;C:\Qt\Tools\Ninja;$env:PATH"

ctest --test-dir "$root\build" --output-on-failure
exit $LASTEXITCODE
