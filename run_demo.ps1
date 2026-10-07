$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

& $python manage.py migrate --noinput --settings=config.settings.demo
if ($LASTEXITCODE -ne 0) {
    throw "Demo database migrations failed."
}

& $python manage.py seed_demo_data --sales 1000 --batch preview --settings=config.settings.demo
if ($LASTEXITCODE -ne 0) {
    throw "Demo data could not be prepared."
}

$createAdmin = Read-Host "Create a demo administrator account now? Press Enter for Yes, or type N"
if ([string]::IsNullOrWhiteSpace($createAdmin) -or $createAdmin -match "^(y|yes)$") {
    & $python manage.py createsuperuser --settings=config.settings.demo
    if ($LASTEXITCODE -ne 0) {
        throw "Demo administrator setup failed."
    }
}

Write-Host ""
Write-Host "Starting Agile Hub with isolated sample records at http://127.0.0.1:8001/"
Write-Host "Keep this window open while using the demo. Press Ctrl+C to stop it."
& $python manage.py runserver 127.0.0.1:8001 --settings=config.settings.demo
if ($LASTEXITCODE -ne 0) {
    throw "The demo server stopped with an error."
}
