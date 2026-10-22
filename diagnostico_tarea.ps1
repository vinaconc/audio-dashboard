$log = "I:\Github\Proyectoaudioacordes\dashboard\diagnostico_tarea.log"
"Inicio: $(Get-Date -Format o)" | Out-File $log -Encoding utf8
"Usuario: $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)" | Out-File $log -Append -Encoding utf8
"Directorio: $((Get-Location).Path)" | Out-File $log -Append -Encoding utf8
"Python existe: $(Test-Path 'I:\Github\Proyectoaudioacordes\dashboard\.venv\Scripts\python.exe')" | Out-File $log -Append -Encoding utf8
"Main existe: $(Test-Path 'I:\Github\Proyectoaudioacordes\dashboard\main.py')" | Out-File $log -Append -Encoding utf8
