@echo off
cd /d "I:\Github\Proyectoaudioacordes\dashboard"
"I:\Github\Proyectoaudioacordes\dashboard\.venv\Scripts\python.exe" -m uvicorn main:app --app-dir "I:\Github\Proyectoaudioacordes\dashboard" --host 127.0.0.1 --port 8012 >> "I:\Github\Proyectoaudioacordes\dashboard\inicio_dashboard_cmd.log" 2>&1
echo Codigo de salida: %ERRORLEVEL%>> "I:\Github\Proyectoaudioacordes\dashboard\inicio_dashboard_cmd.log"
