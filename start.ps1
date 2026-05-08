# Colors
function Write-Color($color, $text) {
    Write-Host $text -ForegroundColor $color
}

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check dependencies
function Test-Command($name, $installHint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Color Red "Error: $name is not installed."
        Write-Host "Install with: $installHint"
        exit 1
    }
}

Test-Command "python" "winget install Python.Python.3.11"
Test-Command "node" "winget install OpenJS.NodeJS"
Test-Command "ffmpeg" "winget install Gyan.FFmpeg"

# Check Python version (3.11+)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
if ($LASTEXITCODE -ne 0) {
    $pyVer = (python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") 2>$null
    if (-not $pyVer) { $pyVer = "unknown" }
    Write-Color Red "Error: Python 3.11+ required, found $pyVer."
    Write-Host "Install with: winget install Python.Python.3.11"
    exit 1
}

# Check Node version (18+)
$nodeMajor = (node -p "process.versions.node.split('.')[0]") 2>$null
if (-not $nodeMajor -or [int]$nodeMajor -lt 18) {
    $nodeVer = (node -v) 2>$null
    if (-not $nodeVer) { $nodeVer = "unknown" }
    Write-Color Red "Error: Node 18+ required, found $nodeVer."
    Write-Host "Install with: winget install OpenJS.NodeJS"
    exit 1
}

# Check for .env file
if (-not (Test-Path "backend\.env")) {
    Write-Color Yellow "No backend\.env file found."
    Write-Host "Creating from .env.example..."
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Color Yellow "Please edit backend\.env and add your YOUTUBE_API_KEY"
    Write-Host "Get one at: https://console.cloud.google.com/"
    Write-Host ""
    Write-Host "Then run .\start.ps1 again."
    exit 1
}

# Verify YOUTUBE_API_KEY is filled in
$apiKeyLine = (Get-Content "backend\.env" | Where-Object { $_ -match "^YOUTUBE_API_KEY=" } | Select-Object -First 1)
if (-not $apiKeyLine -or $apiKeyLine -eq "YOUTUBE_API_KEY=" -or $apiKeyLine -eq "YOUTUBE_API_KEY=your-youtube-api-key") {
    Write-Color Red "Error: YOUTUBE_API_KEY in backend\.env is not set."
    Write-Host "Edit backend\.env and add your YouTube Data API key."
    Write-Host "Get one at: https://console.cloud.google.com/"
    exit 1
}

# Check ports are free
function Test-Port($port) {
    $inUse = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($inUse) {
        Write-Color Red "Error: Port $port is already in use."
        Write-Host "Find process: Get-NetTCPConnection -LocalPort $port"
        exit 1
    }
}
Test-Port 8000
Test-Port 5173

Write-Color Green "Starting Scribr..."

# Setup backend
Push-Location backend

# Create venv if it doesn't exist
if (-not (Test-Path ".venv") -and -not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
}

# Activate venv
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & .venv\Scripts\Activate.ps1
} elseif (Test-Path "venv\Scripts\Activate.ps1") {
    & venv\Scripts\Activate.ps1
}

# Install/update Python dependencies
Write-Host "Installing Python dependencies..."
pip install --progress-bar on -r requirements.txt

# Start backend
Write-Host "Starting backend..."
$backend = Start-Process python -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" -PassThru -NoNewWindow
Pop-Location

# Start frontend
Write-Host "Starting frontend..."
Push-Location frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing frontend dependencies..."
    npm install
}

$frontend = Start-Process npm -ArgumentList "run", "dev" -PassThru -NoNewWindow
Pop-Location

Write-Host ""
Write-Color Green "Scribr is running:"
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  Database: backend/scribr.db (SQLite)"
Write-Host ""
Write-Host "Press Ctrl+C to stop"

# Cleanup on exit
try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Write-Color Yellow "Stopping services..."
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
    Write-Color Green "Stopped."
}
