#!/usr/bin/env powershell

# Run GPU Docker Compose Configuration
# This script starts the Speak AI application using GPU acceleration

param(
    [switch]$Down,
    [switch]$Build,
    [switch]$Logs,
    [switch]$Status,
    [switch]$Help
)

# Color output functions
function Write-Success { param($Message) Write-Host $Message -ForegroundColor Green }
function Write-Error { param($Message) Write-Host $Message -ForegroundColor Red }
function Write-Info { param($Message) Write-Host $Message -ForegroundColor Cyan }
function Write-Warning { param($Message) Write-Host $Message -ForegroundColor Yellow }

# Help function
function Show-Help {
    Write-Host ""
    Write-Info "Speak AI GPU Docker Compose Runner"
    Write-Host ""
    Write-Host "Usage: .\run_gpu.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Build     Build and start services"
    Write-Host "  -Down      Stop and remove services"
    Write-Host "  -Logs      Show service logs"
    Write-Host "  -Status    Show service status"
    Write-Host "  -Help      Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\run_gpu.ps1           # Start services"
    Write-Host "  .\run_gpu.ps1 -Build    # Build and start services"
    Write-Host "  .\run_gpu.ps1 -Down     # Stop services"
    Write-Host "  .\run_gpu.ps1 -Logs     # View logs"
    Write-Host ""
}

# Check if help is requested
if ($Help) {
    Show-Help
    exit 0
}

# Check if Docker is installed and running
function Test-Docker {
    try {
        $null = docker --version 2>$null
        $null = docker-compose --version 2>$null
        Write-Success "✓ Docker and Docker Compose are available"
        return $true
    }
    catch {
        Write-Error "✗ Docker or Docker Compose not found. Please install Docker Desktop."
        return $false
    }
}

# Check if .env file exists
function Test-Environment {
    if (-not (Test-Path ".env")) {
        Write-Warning "⚠ .env file not found. Using default environment variables."
        if (Test-Path "env.example") {
            Write-Info "Consider copying env.example to .env and configuring your settings."
        }
    } else {
        Write-Success "✓ .env file found"
    }
}

# Check GPU availability
function Test-GPU {
    try {
        $result = docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "✓ NVIDIA GPU support is available"
            return $true
        } else {
            Write-Warning "⚠ GPU support test failed, but will attempt to run anyway"
            return $false
        }
    }
    catch {
        Write-Warning "⚠ Could not verify GPU support, but will attempt to run anyway"
        return $false
    }
}

# Main execution
Write-Info "=== Speak AI GPU Docker Compose Runner ==="
Write-Host ""

# Perform pre-flight checks
if (-not (Test-Docker)) {
    exit 1
}

Test-Environment
Test-GPU

Write-Host ""

# Handle different operations
if ($Down) {
    Write-Info "Stopping and removing services..."
    docker-compose -f docker-compose.gpu.yml down
    if ($LASTEXITCODE -eq 0) {
        Write-Success "✓ Services stopped successfully"
    } else {
        Write-Error "✗ Failed to stop services"
        exit 1
    }
}
elseif ($Logs) {
    Write-Info "Showing service logs (Ctrl+C to exit)..."
    docker-compose -f docker-compose.gpu.yml logs -f
}
elseif ($Status) {
    Write-Info "Service status:"
    docker-compose -f docker-compose.gpu.yml ps
}
elseif ($Build) {
    Write-Info "Building and starting services with GPU acceleration..."
    docker-compose -f docker-compose.gpu.yml up --build -d
    if ($LASTEXITCODE -eq 0) {
        Write-Success "✓ Services built and started successfully"
        Write-Info "Backend available at: http://localhost:9000"
        Write-Info "TTS Service available at: http://localhost:8880"
        Write-Host ""
        Write-Info "To view logs: .\run_gpu.ps1 -Logs"
        Write-Info "To stop services: .\run_gpu.ps1 -Down"
    } else {
        Write-Error "✗ Failed to build and start services"
        exit 1
    }
}
else {
    Write-Info "Starting services with GPU acceleration..."
    docker-compose -f docker-compose.gpu.yml up -d
    if ($LASTEXITCODE -eq 0) {
        Write-Success "✓ Services started successfully"
        Write-Info "Backend available at: http://localhost:9000"
        Write-Info "TTS Service available at: http://localhost:8880"
        Write-Host ""
        Write-Info "To view logs: .\run_gpu.ps1 -Logs"
        Write-Info "To stop services: .\run_gpu.ps1 -Down"
    } else {
        Write-Error "✗ Failed to start services"
        Write-Info "Try running with -Build flag to rebuild images"
        exit 1
    }
}

Write-Host "" 