#Requires -Version 5.1
<#
.SYNOPSIS
    Complete setup script for Vibe-Quality-Searcharr on Windows

.DESCRIPTION
    This script automates the complete setup process:
    - Checks prerequisites (Docker, Docker Compose)
    - Creates required directories (data, secrets)
    - Generates secure encryption keys
    - Optionally builds and starts the application

.EXAMPLE
    .\setup-windows.ps1
    Runs the complete setup with prompts

.EXAMPLE
    .\setup-windows.ps1 -AutoStart
    Runs setup and automatically starts the application

.NOTES
    Version: 1.0.0
    Author: Vibe-Quality-Searcharr
    Requires: PowerShell 5.1+, Docker Desktop
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [switch]$AutoStart,

    [Parameter(Mandatory=$false)]
    [switch]$SkipSecrets
)

# Set strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-WarningMsg {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-InfoMsg {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "================================================================" -ForegroundColor Blue
    Write-Host ""
}

function Test-CommandExists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-DockerRunning {
    try {
        $null = docker ps 2>&1
        return $true
    }
    catch {
        return $false
    }
}

# Main setup
try {
    Write-Header "Vibe-Quality-Searcharr - Windows Setup"

    Write-InfoMsg "This script will set up Vibe-Quality-Searcharr on your system."
    Write-Host ""

    # Check PowerShell version
    $psVersion = $PSVersionTable.PSVersion
    Write-InfoMsg "PowerShell Version: $($psVersion.Major).$($psVersion.Minor)"

    if ($psVersion.Major -lt 5) {
        Write-ErrorMsg "PowerShell 5.1 or higher is required. Current version: $psVersion"
        exit 1
    }

    Write-Host ""
    Write-Host "Step 1: Checking Prerequisites" -ForegroundColor White
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host ""

    # Check Docker
    Write-InfoMsg "Checking for Docker..."
    if (-not (Test-CommandExists "docker")) {
        Write-ErrorMsg "Docker is not installed or not in PATH"
        Write-Host ""
        Write-Host "Please install Docker Desktop from:" -ForegroundColor Yellow
        Write-Host "  https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
        Write-Host ""
        exit 1
    }
    Write-Success "Docker found: $(docker --version)"

    # Check Docker Compose
    Write-InfoMsg "Checking for Docker Compose..."
    if (-not (Test-CommandExists "docker-compose")) {
        Write-ErrorMsg "Docker Compose is not installed or not in PATH"
        Write-Host ""
        Write-Host "Docker Compose is usually included with Docker Desktop." -ForegroundColor Yellow
        Write-Host "Please ensure Docker Desktop is properly installed." -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
    Write-Success "Docker Compose found: $(docker-compose --version)"

    # Check if Docker is running
    Write-InfoMsg "Checking if Docker is running..."
    if (-not (Test-DockerRunning)) {
        Write-ErrorMsg "Docker is not running"
        Write-Host ""
        Write-Host "Please start Docker Desktop and wait for it to be ready." -ForegroundColor Yellow
        Write-Host "Then run this script again." -ForegroundColor Yellow
        Write-Host ""
        exit 1
    }
    Write-Success "Docker is running"

    Write-Host ""
    Write-Host "Step 2: Creating Required Directories" -ForegroundColor White
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host ""

    # Get script directory (parent of scripts folder)
    $scriptDir = Split-Path -Parent $PSScriptRoot
    Push-Location $scriptDir

    try {
        # Create data directory
        Write-InfoMsg "Creating data directory..."
        $dataDir = Join-Path $scriptDir "data"
        if (-not (Test-Path $dataDir)) {
            $null = New-Item -ItemType Directory -Path $dataDir -Force
            Write-Success "Created: $dataDir"
        }
        else {
            Write-InfoMsg "Data directory already exists: $dataDir"
        }

        # Create secrets directory (will be populated by generate-secrets.ps1)
        Write-InfoMsg "Creating secrets directory..."
        $secretsDir = Join-Path $scriptDir "secrets"
        if (-not (Test-Path $secretsDir)) {
            $null = New-Item -ItemType Directory -Path $secretsDir -Force
            Write-Success "Created: $secretsDir"
        }
        else {
            Write-InfoMsg "Secrets directory already exists: $secretsDir"
        }

        Write-Host ""
        Write-Host "Step 3: Fixing Shell Script Line Endings" -ForegroundColor White
        Write-Host "----------------------------------------" -ForegroundColor Gray
        Write-Host ""

        # Fix line endings for shell scripts (Git on Windows uses CRLF, Docker needs LF)
        Write-InfoMsg "Converting shell scripts to Unix line endings..."
        $shellScripts = Get-ChildItem -Path $scriptDir -Filter "*.sh" -Recurse -File
        $fixedCount = 0
        foreach ($script in $shellScripts) {
            try {
                $content = Get-Content -Raw $script.FullName
                if ($content -match "`r`n") {
                    $content = $content -replace "`r`n", "`n"
                    [System.IO.File]::WriteAllText($script.FullName, $content)
                    $fixedCount++
                    Write-InfoMsg "Fixed: $($script.Name)"
                }
            }
            catch {
                Write-WarningMsg "Could not fix line endings for: $($script.Name)"
            }
        }

        if ($fixedCount -gt 0) {
            Write-Success "Fixed line endings in $fixedCount shell script(s)"
        }
        else {
            Write-InfoMsg "All shell scripts already have correct line endings"
        }

        Write-Host ""
        Write-Host "Step 4: Generating Encryption Keys" -ForegroundColor White
        Write-Host "----------------------------------------" -ForegroundColor Gray
        Write-Host ""

        if ($SkipSecrets) {
            Write-WarningMsg "Skipping secret generation (--SkipSecrets flag used)"
        }
        else {
            # Check if secrets already exist
            $secretFiles = @("db_key.txt", "secret_key.txt", "pepper.txt")
            $existingSecrets = @()
            foreach ($file in $secretFiles) {
                $filePath = Join-Path $secretsDir $file
                if (Test-Path $filePath) {
                    $existingSecrets += $file
                }
            }

            if ($existingSecrets.Count -gt 0) {
                Write-InfoMsg "Some secret files already exist:"
                foreach ($file in $existingSecrets) {
                    Write-Host "  - $file" -ForegroundColor Gray
                }
                Write-Host ""
                Write-Host "The generate-secrets script will prompt you before overwriting." -ForegroundColor Cyan
                Write-Host ""
            }

            # Run generate-secrets.ps1
            $generateSecretsScript = Join-Path $PSScriptRoot "generate-secrets.ps1"
            if (Test-Path $generateSecretsScript) {
                Write-InfoMsg "Running secret generation script..."
                Write-Host ""
                & $generateSecretsScript

                if ($LASTEXITCODE -ne 0) {
                    Write-ErrorMsg "Secret generation failed"
                    exit 1
                }
            }
            else {
                Write-ErrorMsg "Cannot find generate-secrets.ps1 script at: $generateSecretsScript"
                exit 1
            }
        }

        Write-Host ""
        Write-Host "Step 5: Docker Setup" -ForegroundColor White
        Write-Host "----------------------------------------" -ForegroundColor Gray
        Write-Host ""

        if ($AutoStart) {
            Write-InfoMsg "Building Docker image..."
            docker-compose build

            if ($LASTEXITCODE -ne 0) {
                Write-ErrorMsg "Docker build failed"
                exit 1
            }

            Write-Success "Docker image built successfully"
            Write-Host ""

            Write-InfoMsg "Starting application..."
            docker-compose up -d

            if ($LASTEXITCODE -ne 0) {
                Write-ErrorMsg "Failed to start application"
                exit 1
            }

            Write-Success "Application started"
            Write-Host ""

            # Wait a moment for startup
            Write-InfoMsg "Waiting for application to initialize..."
            Start-Sleep -Seconds 5

            # Check status
            Write-InfoMsg "Checking container status..."
            docker-compose ps
        }
        else {
            Write-InfoMsg "Skipping automatic start (use -AutoStart to build and start automatically)"
        }

        Write-Host ""
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host "Setup Complete!" -ForegroundColor Green
        Write-Host "================================================================" -ForegroundColor Green
        Write-Host ""

        if ($AutoStart) {
            Write-Host "Next Steps:" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  1. Check the application logs:" -ForegroundColor White
            Write-Host "     docker-compose logs -f" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  2. Open your browser to:" -ForegroundColor White
            Write-Host "     http://localhost:7337" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  3. Follow the setup wizard to create your admin account" -ForegroundColor White
            Write-Host ""
        }
        else {
            Write-Host "Next Steps:" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  1. Build the Docker image:" -ForegroundColor White
            Write-Host "     docker-compose build" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  2. Start the application:" -ForegroundColor White
            Write-Host "     docker-compose up -d" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  3. Check the logs:" -ForegroundColor White
            Write-Host "     docker-compose logs -f" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  4. Open your browser to:" -ForegroundColor White
            Write-Host "     http://localhost:7337" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "  Or run this script again with -AutoStart to do all of this automatically." -ForegroundColor Yellow
            Write-Host ""
        }

        Write-Host "For troubleshooting, see: docs/how-to-guides/troubleshoot.md" -ForegroundColor Gray
        Write-Host ""

        exit 0
    }
    finally {
        Pop-Location
    }
}
catch {
    $errorMsg = $_.Exception.Message
    $stackTrace = $_.ScriptStackTrace
    Write-ErrorMsg "Setup failed: $errorMsg"
    Write-Host $stackTrace -ForegroundColor Red
    Write-Host ""
    Write-Host "For help, see: docs/how-to-guides/troubleshoot.md" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
