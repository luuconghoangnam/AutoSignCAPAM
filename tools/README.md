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
