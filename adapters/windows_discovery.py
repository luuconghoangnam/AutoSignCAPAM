"""Multi-source absolute executable discovery for supported Windows products."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveryResult:
    executable: Path
    source: str
    install_root: Path


def _valid(path, filename: str) -> Path | None:
    try:
        candidate = Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve(strict=True)
        if candidate.is_file() and candidate.name.lower() == filename.lower():
            return candidate
    except (OSError, RuntimeError):
        pass
    return None


def _product_identity_ok(path: Path, product: str) -> bool:
    """Validate version-resource product/company when metadata is available."""
    try:
        import win32api

        info = win32api.GetFileVersionInfo(str(path), "\\VarFileInfo\\Translation")
        if not info:
            return False
        language, codepage = info[0]
        prefix = f"\\StringFileInfo\\{language:04x}{codepage:04x}"
        values = []
        for key in ("CompanyName", "ProductName", "FileDescription", "OriginalFilename"):
            try:
                values.append(str(win32api.GetFileVersionInfo(str(path), f"{prefix}\\{key}")))
            except Exception:
                continue
        text = " ".join(values).lower()
        expected = (
            ("capam", "pam client", "privileged access manager", "ca inc", "broadcom", "symantec")
            if product == "capam"
            else ("globalprotect", "palo alto", "pangpa.exe")
        )
        return any(token in text for token in expected)
    except Exception:
        return False


def _registry_candidates(product: str, filename: str):
    try:
        import winreg
    except ImportError:
        return
    views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
    hives = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
    vendor_keys = {
        "capam": (r"SOFTWARE\Broadcom\CAPAM Client", r"SOFTWARE\CA\CAPAM Client"),
        "gp": (r"SOFTWARE\Palo Alto Networks\GlobalProtect\PanSetup",),
    }[product]
    for hive in hives:
        for view in views:
            for subkey in vendor_keys:
                try:
                    with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as key:
                        for value_name in ("InstallPath", "InstallLocation", "Path"):
                            try:
                                value, _ = winreg.QueryValueEx(key, value_name)
                                yield Path(value) / filename, f"registry:{subkey}:{value_name}"
                            except OSError:
                                continue
                except OSError:
                    continue
            app_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{filename}"
            try:
                with winreg.OpenKey(hive, app_path, 0, winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    yield Path(str(value).strip('"')), "registry:app-paths"
            except OSError:
                pass
            uninstall = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
            try:
                with winreg.OpenKey(hive, uninstall, 0, winreg.KEY_READ | view) as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            name = winreg.EnumKey(root, index)
                            with winreg.OpenKey(root, name) as entry:
                                display, _ = winreg.QueryValueEx(entry, "DisplayName")
                                publisher = ""
                                try:
                                    publisher, _ = winreg.QueryValueEx(entry, "Publisher")
                                except OSError:
                                    pass
                                text = f"{display} {publisher}".lower()
                                expected = (
                                    ("privileged access manager", "capam", "ca pam")
                                    if product == "capam" else ("globalprotect", "palo alto")
                                )
                                if not any(token in text for token in expected):
                                    continue
                                try:
                                    location, _ = winreg.QueryValueEx(entry, "InstallLocation")
                                    if location:
                                        yield Path(location) / filename, "registry:uninstall-location"
                                except OSError:
                                    pass
                                try:
                                    icon, _ = winreg.QueryValueEx(entry, "DisplayIcon")
                                    icon_path = str(icon).split(",", 1)[0].strip().strip('"')
                                    if icon_path:
                                        yield Path(icon_path), "registry:uninstall-icon"
                                except OSError:
                                    pass
                        except OSError:
                            continue
            except OSError:
                pass


def _known_folder_candidates(product: str, filename: str):
    roots = []
    for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        if os.environ.get(name):
            roots.append(Path(os.environ[name]))
    layouts = (
        ("Broadcom", "CAPAM Client"), ("CA", "CAPAM Client")
    ) if product == "capam" else (("Palo Alto Networks", "GlobalProtect"),)
    for root in roots:
        for layout in layouts:
            yield root.joinpath(*layout, filename), "known-folder"
    if product == "capam":
        profile = Path.home()
        yield profile / "CA PAM Client" / filename, "profile-layout"
        yield profile / "CAPAM Client" / filename, "profile-layout"


def _running_process_candidate(process_name: str):
    try:
        import win32api
        import win32con
        import win32process

        for pid in win32process.EnumProcesses():
            handle = None
            try:
                handle = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                path = Path(win32process.GetModuleFileNameEx(handle, 0))
                if path.name.lower() == process_name.lower():
                    return path
            except Exception:
                continue
            finally:
                if handle:
                    handle.Close()
    except Exception:
        pass
    return None


def _gp_service_candidate():
    try:
        import win32service

        manager = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        service = win32service.OpenService(manager, "PanGPS", win32service.SERVICE_QUERY_CONFIG)
        try:
            command = win32service.QueryServiceConfig(service)[3]
            match = re.match(r'^"([^"]+)"|^(\S+)', command)
            if match:
                service_exe = Path(match.group(1) or match.group(2))
                return service_exe.parent / "PanGPA.exe"
        finally:
            win32service.CloseServiceHandle(service)
            win32service.CloseServiceHandle(manager)
    except Exception:
        return None


def discover(product: str) -> DiscoveryResult | None:
    filename = "CAPAMClient.exe" if product == "capam" else "PanGPA.exe"
    running = _running_process_candidate(filename)
    if (candidate := _valid(running, filename)) and _product_identity_ok(candidate, product):
        return DiscoveryResult(candidate, "running-process", candidate.parent)
    candidates = list(_registry_candidates(product, filename) or [])
    if product == "gp" and (service := _gp_service_candidate()):
        candidates.append((service, "service:PanGPS"))
    candidates.extend(_known_folder_candidates(product, filename))
    for path, source in candidates:
        if (candidate := _valid(path, filename)) and _product_identity_ok(candidate, product):
            return DiscoveryResult(candidate, source, candidate.parent)
    return None
