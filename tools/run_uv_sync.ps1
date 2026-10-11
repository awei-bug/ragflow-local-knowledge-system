$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $root "pyproject.toml"))) {
  $root = (Get-Location).Path
}
Set-Location $root
$uv = "D:\学习\Anaconda\Scripts\uv.exe"
$log = Join-Path $root "uv_sync_bg.log"
$err = Join-Path $root "uv_sync_bg.err"
"START $(Get-Date -Format o)" | Out-File -FilePath $log -Encoding utf8
"" | Out-File -FilePath $err -Encoding utf8
& $uv sync --python 3.13 1>> $log 2>> $err
$code = $LASTEXITCODE
"EXIT $code $(Get-Date -Format o)" | Out-File -FilePath $log -Append -Encoding utf8
exit $code
