@echo off
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   DocuSense System     ║
echo  ║   Starting server...                 ║
echo  ╚══════════════════════════════════════╝
echo.
echo  Open your browser at: http://localhost:8000
echo  Press Ctrl+C to stop the server
echo.
uvicorn src.web:app --host 0.0.0.0 --port 8000
