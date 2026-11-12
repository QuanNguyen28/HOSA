param([switch]$New, [string]$Model = '', [switch]$Strict)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

# Configure this console session only; no system-wide locale change.
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& (Join-Path $env:SystemRoot 'System32\chcp.com') 65001 | Out-Null
$Host.UI.RawUI.WindowTitle = 'HOSA LLM - UTF8'

$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$chatPath = Join-Path $projectRoot 'scripts\assistant_chat.py'
$capabilitiesUrl = 'http://127.0.0.1:8000/api/assistant/capabilities'
$capabilities = $null
try { $capabilities = Invoke-RestMethod -Uri $capabilitiesUrl -TimeoutSec 2 } catch {}
if (-not $capabilities) {
    $cachePath = Join-Path $projectRoot 'data\cache\assistant'
    New-Item -ItemType Directory -Force -Path $cachePath | Out-Null
    $env:ASSISTANT_ENABLED = 'true'
    if ($Model) {
        $env:ASSISTANT_PROVIDER = 'nvidia'
        $env:NVIDIA_MODEL = $Model
    }
    if ($Strict) { $env:ASSISTANT_FAILOVER_ENABLED = 'false' }
    $logPrefix = Join-Path $cachePath ('terminal-api-' + $PID)
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput ($logPrefix + '.out.log') -RedirectStandardError ($logPrefix + '.err.log')
    for ($attempt = 0; $attempt -lt 15; $attempt++) {
        Start-Sleep -Seconds 1
        try { $capabilities = Invoke-RestMethod -Uri $capabilitiesUrl -TimeoutSec 2; break } catch {}
        if ($backendProcess.HasExited) { break }
    }
    if (-not $capabilities) {
        throw ('Local API could not start. See ' + $logPrefix + '.err.log')
    }
}

if ($Model -and $capabilities.primary_model -ne $Model) {
    throw ('The running API uses ' + $capabilities.primary_model + '. Restart that API with the requested model before using -Model.')
}
if ($Strict -and $capabilities.fallback_model) {
    throw 'The running API has failover enabled. Restart it with ASSISTANT_FAILOVER_ENABLED=false before using -Strict.'
}
$Host.UI.RawUI.WindowTitle = 'HOSA LLM - ' + $capabilities.primary_model + ' - UTF8'

if ($New) {
    & $pythonPath -X utf8 $chatPath --new
} else {
    & $pythonPath -X utf8 $chatPath
}
