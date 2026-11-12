<#
.SYNOPSIS
  Starts the throw-away MariaDB + Redis (docker/docker-compose.test.yml), runs the real-services tests and always
  removes the containers and volumes afterwards.
.DESCRIPTION
  Run it from an activated Python virtual environment: it uses whatever `python` is on the PATH.
  Extra arguments go straight to pytest.
.EXAMPLE
  .\scripts\run_services_tests.ps1
.EXAMPLE
  .\scripts\run_services_tests.ps1 -k redis -x
.EXAMPLE
  .\scripts\run_services_tests.ps1 -m "services and not resilience"
#>
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$compose = @('compose', '-f', 'docker/docker-compose.test.yml')
$previous = $env:RUN_INTEGRATION_TESTS
$exitCode = 1

try {
    Write-Host '==> Starting test containers (MariaDB, Redis)'
    docker @compose up -d --wait
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the test containers' }

    Write-Host "==> Running services tests with $((Get-Command python).Source)"
    $env:RUN_INTEGRATION_TESTS = '1'
    python -m pytest tests/integration/services -m services -v @args
    $exitCode = $LASTEXITCODE
}
catch {
    Write-Error $_
}
finally {
    Write-Host '==> Removing test containers and volumes'
    docker @compose down -v --remove-orphans
    if ($null -eq $previous) { Remove-Item Env:RUN_INTEGRATION_TESTS -ErrorAction SilentlyContinue }
    else { $env:RUN_INTEGRATION_TESTS = $previous }
}
exit $exitCode
