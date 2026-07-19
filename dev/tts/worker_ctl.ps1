# worker_ctl.ps1 - fluid start/stop of a Windows TTS fleet worker (laptop 4070).
# The queue makes stops safe: an abrupt stop's in-flight items (<=5 generated,
# <=one batch claimed) re-serve after the 30-min lease, and MSL's maintain loop
# reconciles anything a stopped worker completed but didn't sync. So "pause" =
# stop, "resume" = start; nothing is lost either way.
#
# Run (execution policy is usually Restricted here, so bypass it):
#   powershell -ExecutionPolicy Bypass -File worker_ctl.ps1 start
#   powershell -ExecutionPolicy Bypass -File worker_ctl.ps1 stop
#   powershell -ExecutionPolicy Bypass -File worker_ctl.ps1 status
param([Parameter(Mandatory)][ValidateSet('start','stop','status')]$cmd)

$cbox    = "$env:USERPROFILE\miniforge3\envs\cbox\python.exe"
$envroot = "$env:USERPROFILE\miniforge3\envs\cbox"
$dir     = "C:\Users\denis\code\library-of-stock\dev\tts"
$work    = "$env:USERPROFILE\los_tts"
$pidfile = "$work\worker.pids"

switch ($cmd) {
  'start' {
    # conda env bin dirs on PATH (direct python.exe doesn't activate the env, and
    # ffmpeg lives in Library\bin - without it the encode step fails WinError 2)
    $env:PATH = "$envroot;$envroot\Library\bin;$envroot\Library\mingw-w64\bin;$envroot\Scripts;$env:PATH"
    $w = Start-Process -FilePath $cbox -WindowStyle Hidden -PassThru `
      -ArgumentList "`"$dir\gen_tts.py`"","--queue","--queue-host","msl","--worker","laptop" `
      -RedirectStandardOutput "$work\gen_laptop.log" -RedirectStandardError "$work\gen_laptop.err"
    $p = Start-Process -FilePath $cbox -WindowStyle Hidden -PassThru `
      -ArgumentList "`"$dir\push_out.py`"","--host","msl" `
      -RedirectStandardOutput "$work\push.log" -RedirectStandardError "$work\push.err"
    "$($w.Id)`n$($p.Id)" | Set-Content $pidfile
    "started: worker PID $($w.Id), push_out PID $($p.Id)"
  }
  'stop' {
    if (Test-Path $pidfile) {
      Get-Content $pidfile | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
      Remove-Item $pidfile
      "stopped (in-flight items re-serve after the lease)"
    } else { "no pidfile; kill python manually if needed" }
  }
  'status' {
    if (Test-Path $pidfile) {
      Get-Content $pidfile | ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime }
    } else { "not running (no pidfile)" }
  }
}
