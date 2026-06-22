"""손(입력): macOS 마우스로 BlueStacks 창을 직접 클릭한다.

이 환경에서 ADB input tap은 막혀 있어(SPEC 2장), 안드로이드 좌표를 macOS 화면 좌표로
변환해 **Quartz 마우스 이벤트**로 클릭한다(cliclick은 클릭당 ~120ms로 느려 교체).
창 위치/크기는 매번 osascript로 읽으므로 창을 옮겨도 동작한다.

게임은 창 안에 **16:9 레터박스로 중앙 배치**된다(2026-06-23 풀스크린/최대화에서 재보정, 매칭0.996).
창이 16:9보다 세로로 길면 상/하 여백, 가로로 길면 좌/우 여백이 생긴다. 창 크기에서 자동 계산하므로
창 이동·리사이즈·전체화면 어디서나 동작한다. (이전 윈도우모드의 타이틀바+우측툴바 가정은 폐기)
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
ASPECT = ANDROID_W / ANDROID_H   # 16:9 게임 렌더 비율

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


def game_rect(geom: tuple[int, int, int, int] | None = None) -> tuple[float, float, float, float]:
    """창 안에서 16:9 게임 렌더 영역 (x0,y0,w,h) in pt (레터박스 중앙배치)."""
    wx, wy, ww, wh = geom or window_geometry()
    if ww / wh >= ASPECT:           # 창이 더 가로로 김 → 좌우 여백(필러박스)
        gh = wh; gw = wh * ASPECT
    else:                           # 창이 더 세로로 김 → 상하 여백(레터박스)
        gw = ww; gh = ww / ASPECT
    return wx + (ww - gw) / 2, wy + (wh - gh) / 2, gw, gh


def android_to_screen(ax: float, ay: float,
                      geom: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """안드로이드 픽셀(ax,ay) -> macOS 클릭 좌표(pt)."""
    gx0, gy0, gw, gh = game_rect(geom)
    cx = gx0 + (ax / ANDROID_W) * gw
    cy = gy0 + (ay / ANDROID_H) * gh
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
