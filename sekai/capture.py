"""화면 읽기(눈): BlueStacks Air의 안드로이드 화면을 ADB screencap으로 가져온다.

이 환경에서 ADB는 screencap만 안정적이고 input/wm/pm 등은 'error: closed'로 막혀 있다(SPEC 2장).
그래서 이 모듈은 '읽기' 전용. '쓰기(클릭)'는 input.py(macOS 마우스)가 담당한다.
"""
from __future__ import annotations
import subprocess
import numpy as np
import cv2

ADB = "/Applications/BlueStacks.app/Contents/MacOS/hd-adb"
DEVICE = "127.0.0.1:5555"   # 5554가 아니라 5555 포트가 LISTEN (SPEC 3.6)

# 안드로이드 렌더 해상도 (실측). 좌표 변환 기준.
ANDROID_W = 1920
ANDROID_H = 1080


def connect() -> None:
    subprocess.run([ADB, "connect", DEVICE],
                   capture_output=True, text=True, timeout=10)


def grab() -> np.ndarray:
    """현재 화면을 BGR ndarray(1080x1920x3)로 반환."""
    p = subprocess.run([ADB, "-s", DEVICE, "exec-out", "screencap", "-p"],
                       capture_output=True, timeout=15)
    if not p.stdout:
        raise RuntimeError(f"screencap 실패: {p.stderr.decode(errors='ignore')}")
    img = cv2.imdecode(np.frombuffer(p.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("PNG 디코드 실패")
    return img


if __name__ == "__main__":
    connect()
    im = grab()
    print("captured", im.shape[1], "x", im.shape[0])
    cv2.imwrite("/tmp/sekai_grab.png", im)
    print("saved /tmp/sekai_grab.png")
