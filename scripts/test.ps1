# Run from any directory: powershell -File scripts/test.ps1
$ErrorActionPreference = 'Stop'
$testComposePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'compose.test.yaml'
$previousTestOrigin = [Environment]::GetEnvironmentVariable('TEST_APP_ORIGIN', 'Process')
$env:TEST_APP_ORIGIN = 'http://frontend-test'

function Invoke-TestCompose {
    param([string[]]$ComposeArguments)
    & docker compose --project-name pokemon-team-builder-tests --file $testComposePath @ComposeArguments
    if ($LASTEXITCODE -ne 0) { throw "Test Compose command failed with exit code $LASTEXITCODE" }
}

try {
    Invoke-TestCompose -ComposeArguments @('build')
    Invoke-TestCompose -ComposeArguments @('up', '-d', '--wait', 'db-test', 'api-test', 'frontend-test')
    Invoke-TestCompose -ComposeArguments @('run', '--rm', 'backend-tests')
    Invoke-TestCompose -ComposeArguments @('run', '--rm', 'frontend-tests')
    Invoke-TestCompose -ComposeArguments @('run', '--rm', 'e2e')
} finally {
    # Only this explicitly named disposable project is stopped. Bind-mounted reports remain.
    & docker compose --project-name pokemon-team-builder-tests --file $testComposePath down
    [Environment]::SetEnvironmentVariable('TEST_APP_ORIGIN', $previousTestOrigin, 'Process')
}
