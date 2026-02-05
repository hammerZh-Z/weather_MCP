$ErrorActionPreference = 'Stop'

param(
  [int]$Port = 8000,
  [int]$Clients = 3,
  [int]$HandshakeSeconds = 2,
  [int]$HoldSeconds = 3
)

function Resolve-VenvPython {
  $py = Join-Path (Get-Location) '.venv\Scripts\python.exe'
  if (!(Test-Path $py)) { throw "Missing venv python at $py" }
  return $py
}

$py = Resolve-VenvPython

$serverStdout = "._tmp_fastmcp_sse_server_out.txt"
$serverStderr = "._tmp_fastmcp_sse_server_err.txt"
Remove-Item -Force -ErrorAction SilentlyContinue $serverStdout, $serverStderr

$server = Start-Process $py `
  -ArgumentList @('exercise\fastmcp_sse.py') `
  -PassThru `
  -RedirectStandardOutput $serverStdout `
  -RedirectStandardError $serverStderr

$clientProcs = @()
try {
  Start-Sleep -Seconds 2

  Write-Host "== 1) SSE handshake =="
  curl.exe -N -H "Accept: text/event-stream" "http://127.0.0.1:$Port/sse" --max-time $HandshakeSeconds

  Write-Host "`n== 2) Open $Clients SSE long connections (hold ~${HoldSeconds}s) =="
  1..$Clients | ForEach-Object {
    $cOut = "._tmp_sse_client_${_}_out.txt"
    $cErr = "._tmp_sse_client_${_}_err.txt"
    Remove-Item -Force -ErrorAction SilentlyContinue $cOut, $cErr
    $cp = Start-Process curl.exe `
      -ArgumentList @('-N','-sS','-H','Accept: text/event-stream',"http://127.0.0.1:$Port/sse",'--max-time',"$($HoldSeconds + 10)") `
      -PassThru `
      -RedirectStandardOutput $cOut `
      -RedirectStandardError $cErr
    $clientProcs += $cp
    Start-Sleep -Milliseconds 250
  }

  Start-Sleep -Seconds $HoldSeconds

  Write-Host "`n== 3) netstat evidence (ESTABLISHED grows with clients) =="
  netstat -ano | findstr ":$Port"

  Write-Host "`n== 4) server logs (tail) =="
  if (Test-Path $serverStdout) { Get-Content $serverStdout -Tail 30 }
  if (Test-Path $serverStderr) { Get-Content $serverStderr -Tail 30 }
}
finally {
  foreach ($cp in $clientProcs) {
    Stop-Process -Id $cp.Id -Force -ErrorAction SilentlyContinue
  }
  Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
}

