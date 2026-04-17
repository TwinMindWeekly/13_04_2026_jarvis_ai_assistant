---
name: windows-shell-fallback
description: "Use this skill when the user wants to perform a Windows system / automation task that no dedicated tool covers — e.g. listing installed apps, querying hardware info, killing a process, managing services, checking disk space, reading environment variables, searching the registry, controlling volume, scheduled tasks, WMI queries, or any other 'ad-hoc Windows operation'. Triggers include mentions of 'powershell', 'cmd', 'registry', 'service', 'process', 'processes', 'kill', 'uninstall', 'installed apps', 'battery', 'disk space', 'system info', 'environment variable', 'task scheduler', 'WMI', 'volume', 'brightness', 'lock screen', combined with a question or an action verb. Do NOT use this skill for actions that have a dedicated tool (launching an app → app_launcher; opening Word/Excel → office_automation; file I/O → file_manager; clipboard → clipboard)."
---

# Windows shell-fallback via PowerShell

## When to use

JARVIS has specialised tools for the most common Windows tasks
(`app_launcher`, `office_automation`, `file_manager`, `clipboard`,
`screenshot`, …). **Always try the specialised tool first.** Only fall
back to `shell_exec` + PowerShell when the task is genuinely ad-hoc:

- Listing installed applications
- Hardware / OS version / battery / RAM / disk queries
- Process control (list, kill, restart)
- Windows services (get status, start, stop)
- Registry queries
- Environment variables (read / set for the current user)
- Scheduled Tasks (list / enable / disable)
- WMI / CIM queries
- Volume / brightness / sleep / lock-screen shortcuts

## Invocation pattern

Use `shell_exec` with a single-line PowerShell command. Prefix with
`powershell -NoProfile -Command` so behaviour is deterministic and the
user's profile scripts don't interfere:

```
shell_exec(command='powershell -NoProfile -Command "<one-liner>"', timeout=15)
```

- `-NoProfile` skips `$PROFILE` scripts (fast, no surprises).
- Short `timeout` (15-30s) — PowerShell startup is ~500 ms, queries rarely exceed 5 s.
- For very small outputs, let the agent read `stdout`. For larger
  results (e.g. installed-app listings), ask PowerShell to narrow the
  output before it crosses the pipe (`Select-Object -First 30`,
  `Where-Object { $_.Name -like "Microsoft*" }`, etc.).

## Recipe matrix

| Goal | PowerShell one-liner |
|------|----------------------|
| List installed apps (64-bit) | `Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* \| Select-Object DisplayName, DisplayVersion \| Where-Object DisplayName \| Sort-Object DisplayName` |
| List Start-Menu apps | `Get-StartApps \| Select-Object Name, AppID` |
| OS + build | `Get-ComputerInfo \| Select-Object OsName, OsVersion, OsBuildNumber, OsArchitecture` |
| Free disk space | `Get-PSDrive -PSProvider FileSystem \| Select-Object Name, @{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}}, @{N='TotalGB';E={[math]::Round(($_.Used+$_.Free)/1GB,1)}}` |
| Top 10 processes by RAM | `Get-Process \| Sort-Object WS -Descending \| Select-Object -First 10 Name, Id, @{N='RAM_MB';E={[math]::Round($_.WS/1MB,1)}}` |
| Kill process by name | `Stop-Process -Name <name> -Force` |
| Service status | `Get-Service <name> \| Select-Object Name, Status, StartType` |
| Start / stop a service | `Start-Service <name>` / `Stop-Service <name>` (needs admin) |
| Read env var | `[Environment]::GetEnvironmentVariable('<NAME>','User')` |
| Set persistent user env var | `[Environment]::SetEnvironmentVariable('<NAME>','<VAL>','User')` |
| List scheduled tasks | `Get-ScheduledTask \| Select-Object TaskName, State \| Where-Object State -eq 'Ready'` |
| Battery level | `(Get-CimInstance Win32_Battery).EstimatedChargeRemaining` |
| Lock workstation | `rundll32.exe user32.dll,LockWorkStation` |
| Current volume (0–100) | `(New-Object -ComObject WScript.Shell).SendKeys([char]175)` (↑) / `[char]174` (↓) / `[char]173` (mute) |

## Output handling

- `shell_exec` returns `stdout`, `stderr`, `exit_code`. Summarise into a
  short natural-language answer for the user — don't dump raw
  PowerShell tables unless the user asked for the raw output.
- If `stderr` contains `Access is denied` or `Requested operation
  requires elevation`, tell the user they need to run JARVIS as
  Administrator to do that specific action. Do NOT silently retry.

## Anti-patterns

- **Don't** use `shell_exec` for tasks that have a dedicated tool.
  Launching Word via `shell_exec "start winword"` is worse than
  `app_launcher(app="word")` because it bypasses resolution logic and
  error handling.
- **Don't** pipe through `cmd /c` if PowerShell can do it directly —
  doubles the startup cost.
- **Don't** put multi-statement scripts in `shell_exec`. If the command
  is more than one statement, use `code_runner` with `language="powershell"`
  instead (cleaner quoting, clearer errors).
- **Don't** run commands that require elevation without warning the user;
  just report the elevation requirement from stderr.
