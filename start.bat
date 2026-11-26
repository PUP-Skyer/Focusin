@echo off
chcp 65001 >nul
echo [聚光 FocusIn] 启动本地服务与 Web 前端...
start "FocusIn backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8765"
start "FocusIn web" cmd /k "cd /d %~dp0web && npm install && npm run dev"
echo 后端: http://127.0.0.1:8765/api/health
echo 前端: http://localhost:5180
