"""손(입력): macOS 마우스로 BlueStacks 창을 직접 클릭한다.

이 환경에서 ADB input tap은 막혀 있어(SPEC 2장), 안드로이드 좌표를 macOS 화면 좌표로
변환해 **Quartz 마우스 이벤트**로 클릭한다(cliclick은 클릭당 ~120ms로 느려 교체).
창 위치/크기는 매번 osascript로 읽으므로 창을 옮겨도 동작한다.

전제: BlueStacks 창은 '논리 포인트' 기준. 창 안에서 게임 렌더 영역은
  - 상단 타이틀바 ~TITLE_PT pt
  - 우측 툴바       ~RIGHT_PT pt
  - 좌/하단은 꽉 참(flush)
2026-06-22 실측 보정으로 도출(SPEC 3.6). 창을 리사이즈해도 크롬이 고정 pt면 유지된다.
"""
from __future__ import annotations
import subprocess
import time
import Quartz
from .capture import ANDROID_W, ANDROID_H


def _post(kind, x, y):
    e = Quartz.CGEventCreateMouseEvent(None, kind, (x, y), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)


def _click(x, y, hold: float = 0.012):
    _post(Quartz.kCGEventLeftMouseDown, x, y)
    time.sleep(hold)
    _post(Quartz.kCGEventLeftMouseUp, x, y)

WINDOW_NAME = "BlueStacks Air"
TITLE_PT = 32     # 상단 타이틀바 높이(pt)
RIGHT_PT = 31     # 우측 툴바 너비(pt)

_GEOM_AS = (
    'tell application "System Events" to tell process "BlueStacks" '
    'to get {position, size} of (first window whose name is "%s")' % WINDOW_NAME
)


def window_geometry() -> tuple[int, int, int, int]:
    """(win_x, win_y, win_w, win_h) in macOS logical points."""
    p = subprocess.run(["osascript", "-e", _GEOM_AS],
                       capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        raise RuntimeError(f"창 위치 조회 실패(손쉬운 사용 권한 확인): {p.stderr.strip()}")
    nums = [int(n) for n in p.stdout.replace(",", " ").split()]
    if len(nums) != 4:
        raise RuntimeError(f"예상치 못한 geometry: {p.stdout!r}")
    return tuple(nums)  # type: ignore[return-value]


def android_to_screen(ax: float, ay: float,
                      geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """안드로이드 픽셀(ax,ay) -> macOS 클릭 좌표(pt)."""
    wx, wy, ww, wh = geom or window_geometry()
    cx = wx + (ax / ANDROID_W) * (ww - RIGHT_PT)
    cy = wy + TITLE_PT + (ay / ANDROID_H) * (wh - TITLE_PT)
    return int(round(cx)), int(round(cy))


def tap(ax: float, ay: float,
        geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """안드로이드 좌표를 macOS 마우스로 클릭(Quartz)."""
    cx, cy = android_to_screen(ax, ay, geom)
    _click(cx, cy)
    return cx, cy


def tap_burst(ax: float, ay: float, n: int = 8, gap_ms: int = 30,
              geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """같은 지점을 n회 빠르게 연타(스토리 진행용). Quartz라 클릭 자체는 거의 공짜."""
    cx, cy = android_to_screen(ax, ay, geom)
    gap = gap_ms / 1000.0
    for i in range(n):
        _click(cx, cy)
        if i < n - 1:
            time.sleep(gap)
    return cx, cy


def swipe(ax1: float, ay1: float, ax2: float, ay2: float,
          steps: int = 8, hold_ms: int = 60,
          geom: tuple[int, int, int, int] | None = None) -> None:
    """안드로이드 좌표 기준 드래그-스와이프(목록 스크롤용). ADB swipe가 막혀서 macOS 드래그로 대체.
    관성 있으니 정확 px 의존 X, '스크롤→캡처→안 변하면 바닥' 루프로 쓸 것."""
    g = geom or window_geometry()
    sx1, sy1 = android_to_screen(ax1, ay1, g)
    sx2, sy2 = android_to_screen(ax2, ay2, g)
    hold = hold_ms / 1000.0
    _post(Quartz.kCGEventLeftMouseDown, sx1, sy1)
    time.sleep(hold)
    for i in range(1, steps + 1):
        ix = round(sx1 + (sx2 - sx1) * i / steps)
        iy = round(sy1 + (sy2 - sy1) * i / steps)
        _post(Quartz.kCGEventLeftMouseDragged, ix, iy)
        time.sleep(0.012)
    time.sleep(hold)
    _post(Quartz.kCGEventLeftMouseUp, sx2, sy2)


if __name__ == "__main__":
    import sys
    g = window_geometry()
    print("window geometry (pt):", g)
    for ax, ay, name in [(0, 0, "TL"), (960, 540, "center"), (1920, 1080, "BR")]:
        print(f"  android({ax},{ay}) [{name}] -> {android_to_screen(ax, ay, g)}")
    if len(sys.argv) == 3:
        print("tapping", tap(float(sys.argv[1]), float(sys.argv[2]), g))
