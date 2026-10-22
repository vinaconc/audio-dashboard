@echo off
cd /d "I:\Github\Proyectoaudioacordes\dashboard"
"I:\Github\Proyectoaudioacordes\dashboard\.venv\Scripts\python.exe" -m uvicorn main:app --app-dir "I:\Github\Proyectoaudioacordes\dashboard" --host 0.0.0.0 --port 8001
