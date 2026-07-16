"""CAPAM Java Access Bridge adapter with an owned message-pump thread."""
from __future__ import annotations

import os
import queue
import re
import tempfile
import threading
from pathlib import Path


class JABUnavailable(RuntimeError):
    pass


class CAPAMJAB:
    """Serialize all JAB calls on one thread that owns the Win32 message pump."""

    def __init__(self, bridge_dll: str):
        if os.name != "nt":
            raise JABUnavailable("CAPAM JAB backend requires Windows")
        self._requests = queue.Queue()
        self._ready = threading.Event()
        self._closed = False
        self._startup_error = None
        self._thread = threading.Thread(
            target=self._thread_main,
            args=(bridge_dll,),
            name="CAPAM-JAB",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(10):
            self.close()
            raise JABUnavailable("JAB message-pump thread did not start")
        if self._startup_error:
            error = self._startup_error
            self.close()
            raise JABUnavailable(str(error)) from error

    @staticmethod
    def find_bridge(capam_exe: str) -> str | None:
        root = Path(capam_exe).resolve().parent
        allowed = (
            root / "runtime-17.0.10_7" / "bin" / "WindowsAccessBridge-64.dll",
            root / "runtime" / "bin" / "WindowsAccessBridge-64.dll",
            root / "jre" / "bin" / "WindowsAccessBridge-64.dll",
        )
        matches = [path for path in allowed if path.is_file()]
        return str(matches[0]) if len(matches) == 1 else None

    def _thread_main(self, bridge_dll: str) -> None:
        try:
            os.environ.setdefault("ROBOT_ARTIFACTS", tempfile.gettempdir())
            os.environ["RC_JAVA_ACCESS_BRIDGE_DLL"] = bridge_dll
            from ctypes import byref, wintypes
            import ctypes
            from JABWrapper.context_tree import ContextTree, SearchElement
            from JABWrapper.jab_wrapper import JavaAccessBridgeWrapper

            self._ctypes = ctypes
            self._byref = byref
            self._wintypes = wintypes
            self._context_tree_type = ContextTree
            self._search_type = SearchElement
            self._wrapper = JavaAccessBridgeWrapper(ignore_callbacks=True)
            self._ready.set()
            user32 = ctypes.windll.user32
            msg = wintypes.MSG()
            while not self._closed:
                while True:
                    try:
                        request = self._requests.get_nowait()
                    except queue.Empty:
                        break
                    if request is None:
                        self._closed = True
                        break
                    fn, result = request
                    try:
                        result.put((True, fn(self._wrapper)))
                    except Exception as exc:
                        result.put((False, exc))
                if self._closed:
                    break
                # Pump pending bridge callbacks without blocking the request queue.
                while user32.PeekMessageW(self._byref(msg), 0, 0, 0, 1):
                    user32.TranslateMessage(self._byref(msg))
                    user32.DispatchMessageW(self._byref(msg))
                self._ctypes.windll.kernel32.Sleep(10)
        except Exception as exc:
            self._startup_error = exc
            self._ready.set()
        finally:
            wrapper = getattr(self, "_wrapper", None)
            if wrapper:
                try:
                    wrapper.shutdown()
                except Exception:
                    pass

    def _call(self, fn, timeout: float = 10):
        if self._closed:
            raise JABUnavailable("JAB adapter is closed")
        result = queue.Queue(maxsize=1)
        self._requests.put((fn, result))
        try:
            ok, value = result.get(timeout=timeout)
        except queue.Empty as exc:
            raise JABUnavailable("JAB command timed out") from exc
        if not ok:
            raise JABUnavailable(str(value)) from value
        return value

    def attach(self, *, hwnd: int | None = None, title: str | None = None) -> None:
        def action(wrapper):
            if hwnd:
                vm_id, context = wrapper.get_accessible_context_from_hwnd(hwnd)
                wrapper.set_hwnd(hwnd)
                wrapper.set_context(vm_id, context)
                return hwnd
            if not title:
                raise RuntimeError("Missing Java window identity")
            wrapper.switch_window_by_title(rf"^{re.escape(title)}$")
            return wrapper.get_current_windows_handle()

        self._hwnd = self._call(action)

    @property
    def hwnd(self):
        return getattr(self, "_hwnd", None)

    def _tree(self, wrapper):
        return self._context_tree_type(wrapper, max_depth=16)

    @staticmethod
    def _normalized_name(value: str) -> str:
        return str(value or "").strip().rstrip(":").strip()

    def _find_node(self, wrapper, role: str, name: str):
        expected = self._normalized_name(name)
        search = self._search_type("role", role, strict=True)
        nodes = [
            node for node in self._tree(wrapper).get_by_attrs([search])
            if self._normalized_name(node.context_info.name) == expected
        ]
        if len(nodes) != 1:
            raise RuntimeError(f"Expected one JAB node role={role!r}, name={name!r}")
        return nodes[0]

    def _find_editable_child(self, wrapper, parent_role: str, parent_name: str):
        parent = self._find_node(wrapper, parent_role, parent_name)
        matches = [
            node for node in parent
            if node is not parent
            and node.context_info.role in ("text", "password text")
            and "editable" in str(node.context_info.states).lower()
        ]
        if len(matches) != 1:
            raise RuntimeError("Expected one editable combo child")
        return matches[0]

    def set_text(self, role: str, name: str, value: str) -> None:
        def action(wrapper):
            node = self._find_node(wrapper, role, name)
            node.request_focus()
            node.insert_text(value)

        self._call(action)

    def bounds(self, role: str, name: str, window_rect: dict) -> tuple[int, int, int, int]:
        def action(wrapper):
            info = self._find_node(wrapper, role, name).context_info
            return (
                int(info.x - window_rect["x"]),
                int(info.y - window_rect["y"]),
                int(info.width),
                int(info.height),
            )

        return self._call(action)

    def set_combo_text(self, name: str, value: str) -> None:
        def action(wrapper):
            node = self._find_editable_child(wrapper, "combo box", name)
            node.request_focus()
            node.insert_text(value)

        self._call(action)

    def click(self, name: str) -> None:
        self._call(lambda wrapper: self._find_node(wrapper, "push button", name).click())

    def has(self, role: str, name: str) -> bool:
        try:
            self._call(lambda wrapper: bool(self._find_node(wrapper, role, name)), timeout=5)
            return True
        except JABUnavailable:
            return False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._requests.put_nowait(None)
        except queue.Full:
            pass
        if threading.current_thread() is not self._thread:
            self._thread.join(timeout=2)
