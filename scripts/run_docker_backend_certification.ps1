param(
    [string]$EnvFile = "backend/fastapi/.env.certification",
    [string]$BaseUrl = "http://127.0.0.1:6969",
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"

Write-Host "[certification] Validating env file..."
python backend/fastapi/scripts/validate_certification_env.py $EnvFile
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$composeInfraArgs = @(
    "-f", "docker-compose.yml",
    "-f", "docker-compose.certification.yml",
    "up", "-d",
    "postgres", "redis"
)

Write-Host "[certification] Starting Docker infra..."
docker compose @composeInfraArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$composeAppArgs = @(
    "-f", "docker-compose.yml",
    "-f", "docker-compose.certification.yml",
    "up", "-d", "--no-deps"
)

if (-not $NoBuild) {
    $composeAppArgs += "--build"
}

$composeAppArgs += @("backend", "celery_worker", "celery_beat")

Write-Host "[certification] Starting Docker certification app services..."
docker compose @composeAppArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[certification] Running static audit..."
$env:PYTHONPATH = "backend/fastapi"
python backend/fastapi/scripts/run_backend_certification.py --env-file $EnvFile --skip-runtime
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[certification] Waiting for backend health..."
$maxAttempts = 60
$attempt = 0
$healthy = $false
while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
    }
    Start-Sleep -Seconds 3
    $attempt += 1
}

if (-not $healthy) {
    Write-Error "[certification] Backend did not become healthy in time."
    exit 1
}

Write-Host "[certification] Running runtime smoke checks..."
python backend/fastapi/scripts/run_backend_certification.py --env-file $EnvFile --base-url $BaseUrl
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[certification] Backend Docker certification flow completed."
