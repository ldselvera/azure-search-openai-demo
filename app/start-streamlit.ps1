# PowerShell script for starting FastAPI backend and Streamlit frontend

$ErrorActionPreference = "Stop"

# cd into the parent directory of the script
Set-Location $PSScriptRoot
Set-Location ..

Write-Host 'Creating python virtual environment ".venv"'
python -m venv .venv

Write-Host ""
Write-Host "Restoring backend python packages"
Write-Host ""

.\.venv\Scripts\python.exe -m pip install -r app\backend\requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to restore backend python packages"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Starting FastAPI backend and Streamlit frontend"
Write-Host ""

Set-Location app\backend

# Start FastAPI backend in background
Write-Host "Starting FastAPI backend on port 8000..."
$backend = Start-Process -FilePath "..\..\..\.venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "fastapi_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload" -PassThru -NoNewWindow

# Wait for backend to start
Start-Sleep -Seconds 3

# Start Streamlit frontend
Write-Host "Starting Streamlit frontend on port 8501..."
Set-Location ..
$env:BACKEND_URL = "http://localhost:8000"
$frontend = Start-Process -FilePath "..\..\.venv\Scripts\streamlit.exe" -ArgumentList "run", "streamlit_app.py", "--server.port", "8501", "--server.address", "localhost" -PassThru -NoNewWindow

Write-Host ""
Write-Host "================================================"
Write-Host "FastAPI backend running at: http://localhost:8000"
Write-Host "Streamlit frontend running at: http://localhost:8501"
Write-Host "================================================"
Write-Host ""
Write-Host "Press Ctrl+C to stop both services"

# Function to cleanup on exit
function Cleanup {
    Write-Host ""
    Write-Host "Stopping services..."
    if ($backend -and !$backend.HasExited) {
        Stop-Process -Id $backend.Id -Force
    }
    if ($frontend -and !$frontend.HasExited) {
        Stop-Process -Id $frontend.Id -Force
    }
}

# Register cleanup on script exit
try {
    # Wait for user to press Ctrl+C
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Check if processes are still running
        if ($backend.HasExited -or $frontend.HasExited) {
            Write-Host "One of the services has stopped unexpectedly"
            break
        }
    }
}
finally {
    Cleanup
}
