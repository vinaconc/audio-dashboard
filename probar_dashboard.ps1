$ErrorActionPreference = "Stop"
$base = "I:\Github\Proyectoaudioacordes\dashboard"
$log = Join-Path $base "inicio_dashboard.log"
Set-Location $base

"Inicio: $(Get-Date -Format o)" | Out-File $log -Encoding utf8
"Usuario: $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)" | Out-File $log -Append -Encoding utf8
"Directorio: $((Get-Location).Path)" | Out-File $log -Append -Encoding utf8

$python = Join-Path $base ".venv\Scripts\python.exe"
"Python existe: $(Test-Path $python)" | Out-File $log -Append -Encoding utf8
"Main existe: $(Test-Path (Join-Path $base 'main.py'))" | Out-File $log -Append -Encoding utf8

& $python -m uvicorn main:app --app-dir $base --host 0.0.0.0 --port 8012 *>> $log
"Uvicorn terminó con código $LASTEXITCODE a las $(Get-Date -Format o)" | Out-File $log -Append -Encoding utf8

