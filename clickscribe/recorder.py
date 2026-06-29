"""全局点击监听 + 自动截图。

基于 macOS 的 CGEventTap（需要「辅助功能」权限）。
每次鼠标左键按下时，截取整屏并记录点击坐标。
"""
from __future__ import annotations

import os
import subprocess
import threading
import time

from Quartz import (  # type: ignore
    CGEventTapCreate,
    CGEventMaskBit,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    kCGEventLeftMouseDown,
    CGEventGetLocation,
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    kCFRunLoopCommonModes,
    CFRunLoopRun,
    CFRunLoopStop,
    CFRunLoopGetCurrent,
    CGEventTapEnable,
)

RECORDING_DIR = os.path.join("sessions", "_recording")


def _screenshot(path: str) -> float:
    """静音截取整屏到 path，并返回 retina scale。

    为保证画质，保留 screencapture 的原始 retina 像素图（不缩放）。
    CGEventGetLocation 返回逻辑 points，后续标注时用 scale 映射到像素坐标。
    """
    subprocess.run(["screencapture", "-x", path], check=True)
    try:
        from AppKit import NSScreen

        return float(NSScreen.mainScreen().backingScaleFactor() or 1.0)
    except Exception:
        return 1.0


class Recorder:
    """后台线程里跑一个 CGEventTap run loop。"""

    def __init__(self, on_step=None):
        self.steps: list[dict] = []
        self.running = False
        self._loop = None
        self._tap = None
        self._thread = None
        self.on_step = on_step  # callback(step_dict)
        os.makedirs(RECORDING_DIR, exist_ok=True)

    @staticmethod
    def permission_ok() -> bool:
        """是否已授予「辅助功能」权限。"""
        try:
            from ApplicationServices import AXIsProcessTrusted

            return bool(AXIsProcessTrusted())
        except Exception:
            return False

    # CGEventTap callback 签名：(proxy, event_type, event, refcon)
    def _callback(self, proxy, event_type, event, refcon):
        if event_type == kCGEventLeftMouseDown and self.running:
            loc = CGEventGetLocation(event)
            x, y = int(loc.x), int(loc.y)
            idx = len(self.steps) + 1
            fname = f"img_{idx:03d}_{time.strftime('%H%M%S')}.png"
            path = os.path.join(RECORDING_DIR, fname)
            try:
                scale = _screenshot(path)
            except Exception as exc:  # 截图失败不阻断录制
                print(f"[clickscribe] 截图失败: {exc}")
                return event
            step = {
                "x": x,
                "y": y,
                "screenshot": fname,
                "ts": time.time(),
                "scale": scale,
                "title": "",
                "description": "",
            }
            self.steps.append(step)
            if self.on_step:
                try:
                    self.on_step(step)
                except Exception:
                    pass
        return event

    def _run_loop(self) -> None:
        tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionListenOnly,
            CGEventMaskBit(kCGEventLeftMouseDown),
            self._callback,
            None,
        )
        if not tap:
            # 通常是缺少「辅助功能」权限
            print("[clickscribe] 无法创建事件监听 —— 请到「系统设置 → 隐私与安全性 → 辅助功能」授权后重试")
            self.running = False
            return
        self._tap = tap
        source = CFMachPortCreateRunLoopSource(None, tap, 0)
        self._loop = CFRunLoopGetCurrent()
        CFRunLoopAddSource(self._loop, source, kCFRunLoopCommonModes)
        CGEventTapEnable(tap, True)
        CFRunLoopRun()

    def start(self) -> None:
        if self.running:
            return
        # 清空旧录制目录
        os.makedirs(RECORDING_DIR, exist_ok=True)
        for fname in os.listdir(RECORDING_DIR):
            try:
                os.remove(os.path.join(RECORDING_DIR, fname))
            except OSError:
                pass
        self.steps = []
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> list[dict]:
        self.running = False
        if self._loop is not None:
            CFRunLoopStop(self._loop)
            self._loop = None
        return self.steps
