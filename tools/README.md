# Windows Tools

Tools collect calibration evidence before hybrid OCR/vision changes. Run from repo root.

Install optional diagnostics dependency:

```powershell
python -m pip install -r tools/requirements-windows.txt
```

## Window inventory

```powershell
python -m tools.collect_windows --list-windows
```

## Safe screenshot and metadata

Capture only pre-credential screens by default:

```powershell
python -m tools.collect_windows --title "GlobalProtect" --capture --stage gp-portal
python -m tools.collect_windows --title "Symantec Privileged Access Manager" --capture --stage capam-address
python -m tools.collect_windows --title "Symantec Privileged Access Manager Client - 10.64.213.188" --capture --stage device-list
```

Output:

```text
artifacts/diagnostics/<UTC timestamp>/
  system.json
  windows.json
  uia.json
  <stage>.png
  manifest.json
```

Targeted runs store only target-window metadata. `--list-windows` prints full inventory to stdout; review it before redirecting to a file because unrelated window titles may contain personal data.

Do not use `--allow-sensitive` unless screenshot has been reviewed and redacted. Tool refuses credential-stage capture by default.

## Java Access Bridge probe

```powershell
python -m tools.collect_windows --title "Symantec Privileged Access Manager" --jab --stage capam-address
```

Probe resolves CAPAM executable and bundled `WindowsAccessBridge-64.dll`, attaches exact HWND and saves role/name/state/geometry only. It never reads accessible control values.

## Template benchmark

```powershell
python -m tools.benchmark_templates artifacts/diagnostics/<timestamp>/device-list.png --device 200
```

Report includes device/RDP scores and matched scale. Use it for Win10 vs Win11 comparison.

## Capture checklist

Collect one run per stage and machine:

- Windows 10 pass machine.
- Windows 11 fail machine.
- Display scale 100/125/150%.
- Font/text scale.
- Resolution and monitor ID.
- CAPAM and GlobalProtect version.
- Exact window title, HWND and rect.

Never collect password, OTP, clipboard content or accessible control values.

## Live flow monitor

Observe app lifecycle, foreground HWND, exact window geometry, network reachability, capture hash/stddev, vision field candidates, UIA/JAB availability and runtime FSM events. Tool never clicks, types, saves screenshots, or reads credential control values.

```powershell
python -m tools.monitor_flow --duration 120 --interval 0.5 --output artifacts/diagnostics/flow-timeline.jsonl
```

For synchronized runtime events, set same session ID and timeline path before starting app:

```powershell
$env:AUTOMATION_SESSION_ID = "run-20260718-01"
$env:AUTOMATION_TIMELINE_PATH = "artifacts/diagnostics/run-20260718-01.jsonl"
python -m tools.monitor_flow --duration 120 --output $env:AUTOMATION_TIMELINE_PATH
python main.py
```

Runtime and monitor records share `session_id`, `utc`, `monotonic`, `sequence`, `source`, and `event`. Merge by `monotonic`; inspect `state_enter`, `state_transition`, `observation`, `vision`, `semantic`, and `run_exception`.

Recommended synchronized launcher:

```powershell
python -m tools.run_debug_flow --duration 300 --interval 0.5
```

Launcher opens GUI for interactive password-prefix/OTP entry and writes `debug-session.json` plus `flow-timeline.jsonl` under one new diagnostic run directory. It never receives credentials through command-line arguments or environment variables.

## Focus/Z-order probe

Inspect foreground owner, window class, Z-order, `WS_EX_TOPMOST`, `WS_EX_NOACTIVATE`, owner HWND, cloaked/minimized state and overlap without clicking:

```powershell
python -m tools.probe_focus
python -m tools.probe_focus --exercise "CAPAM AutoSign" --duration 3
```

`--exercise` only requests foreground for exact title and records which window takes focus back. It does not minimize, click, or type.

## Runtime safety diagnostics

Runtime window references now include exact HWND, PID, process creation time, executable, class, title, owner, outer rect and physical client rect. Timeline records discovery provenance, identity validation failures, focus results and elapsed timing without credential values.

Executable discovery does not assume `C:` and does not run bare filenames. Sources, in priority order:

- Existing trusted process image.
- Vendor registry and App Paths in 32-bit/64-bit views.
- Windows uninstall registry `InstallLocation`/`DisplayIcon`.
- GlobalProtect `PanGPS` service install root.
- Actual Program Files environment folders on any drive.
- Supported per-user CAPAM layouts.

Candidates must resolve to an existing regular file with exact expected executable name before launch.

GlobalProtect callback handling does not modify portal policy or delete `gpwelcome.html`. When enabled, runtime closes only a foreground browser tab whose process is an approved browser and whose exact live title contains `GlobalProtect`. It revalidates the same HWND/PID/process immediately before `Ctrl+W`; unrelated browser tabs/windows are untouched.
