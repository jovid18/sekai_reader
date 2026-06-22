"""순회 오케스트레이션 (SPEC 로드맵 5).

scan_character(): 현재 캐릭터의 에피소드 목록을 맨 위부터 스크롤하며 SKIP(미열람)을 전부 읽어 제거.
- 목록은 길어 스크롤 필요. 스크롤은 macOS 드래그(input.swipe), 바닥은 '스크롤해도 화면 안 변함'으로 감지.
- read_one 후 스크롤 위치가 바뀔 수 있어, 매번 맨 위로 올린 뒤 첫 SKIP을 찾아 읽는다(결정적).
"""
from __future__ import annotations
import time
import numpy as np
import cv2
from . import capture, recognize as rec, reader
from . import input as inp

# 스크롤 제스처(안드로이드 px)
# 위로 올리기(맨 위 복귀)는 크고 빠르게. 아래 스캔은 작고 느리게(관성↓·겹침 확보)해 SKIP행을 건너뛰지 않게.
_UP_FROM, _UP_TO = (960, 320), (960, 860)        # drag down = 위로 스크롤
_DOWN_FROM, _DOWN_TO = (960, 760), (960, 460)    # drag up = 아래로 스크롤(겹침 큼, ~1행)
_DOWN_STEPS, _DOWN_HOLD = 8, 110                  # 느리게 → 관성 최소화
_SETTLE = 0.7   # 스크롤 후 안정 대기


def _scroll_down(geom):
    inp.swipe(*_DOWN_FROM, *_DOWN_TO, steps=_DOWN_STEPS, hold_ms=_DOWN_HOLD, geom=geom)
    time.sleep(_SETTLE)


def _sig(img: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = rec.BTN_REGION
    g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (96, 64), interpolation=cv2.INTER_AREA).astype(np.float32)


def screens_equal(a: np.ndarray, b: np.ndarray, thr: float = 6.0) -> bool:
    return float(np.mean((_sig(a) - _sig(b)) ** 2)) < thr


def grab_settled(tries: int = 8) -> np.ndarray:
    """화면이 멈출 때까지(연속 2프레임 동일) 기다린 뒤 그 프레임 반환.
    스크롤 관성으로 움직이는 중에 좌표를 잡아 탭하면 빗나가므로, 탭 전 반드시 안정화한다."""
    prev = capture.grab()
    for _ in range(tries):
        time.sleep(0.22)
        cur = capture.grab()
        if screens_equal(prev, cur):
            return cur
        prev = cur
    return prev


def scroll_to_top(geom, log=print, max_swipes: int = 25) -> np.ndarray:
    prev = capture.grab()
    for _ in range(max_swipes):
        inp.swipe(*_UP_FROM, *_UP_TO, geom=geom)
        time.sleep(_SETTLE)
        cur = capture.grab()
        if screens_equal(prev, cur):
            return cur
        prev = cur
    log("⚠️ scroll_to_top: max_swipes 도달")
    return prev


# SKIP 버튼이 이 y(안드로이드 px)보다 아래면 화면 가장자리라 탭이 빗나가기 쉽다 →
# 한 칸 스크롤해 중앙으로 끌어올린 뒤 탭. 읽을 수 있는 SKIP 아래엔 항상 잠긴 에피소드가 있어
# (=더 스크롤할 여지가 있어) 끌어올리기가 거의 항상 가능하다.
SAFE_MAX_Y = 720


def scan_character(geom=None, log=print, max_episodes: int = 80) -> int:
    """현재 캐릭터의 SKIP을 전부 읽어 제거. 읽은 편수 반환.

    한 방향 sweep: 스토리를 읽고 목록으로 돌아오면 스크롤 위치가 그대로 유지되므로,
    매번 맨 위로 올리지 않고 '현재 뷰에서 남은 SKIP을 바로 처리 → 없으면 아래로 한 칸' 한다.
    (가장자리 y>SAFE_MAX_Y SKIP은 한 칸 스크롤해 중앙으로 끌어올린 뒤 탭)
    """
    geom = geom or inp.window_geometry()
    scroll_to_top(geom, log)          # 시작은 맨 위에서(위쪽 SKIP 누락 방지)
    done = 0
    fails = 0
    while done < max_episodes:
        img = grab_settled()
        ts = sorted(rec.skip_targets(img), key=lambda t: t[1])
        safe = [t for t in ts if t[1] <= SAFE_MAX_Y]
        if safe:
            tgt = safe[0]
            log(f"[{done+1}] SKIP 처리 @ {tgt}")
            if reader.read_one(tgt, geom=geom, log=log):
                done += 1
                fails = 0
            else:
                fails += 1
                log(f"⚠️ read_one 실패 (연속 {fails})")
                if fails >= 4:
                    log("⚠️ 연속 실패 4회 — 중단(미처리 SKIP 남았을 수 있음)")
                    break
            continue   # 위치 유지됨 → 같은 뷰 재스캔(불필요한 맨위 복귀 안 함)
        # 현재 뷰에 안전한 SKIP 없음 → 아래로 한 칸 (가장자리 SKIP은 끌어올려짐)
        prev = img
        _scroll_down(geom)
        nxt = grab_settled()
        if screens_equal(prev, nxt):       # 더 못 내려감 = 바닥
            if ts:                         # 바닥인데 가장자리 SKIP이 남아있으면 best-effort
                log(f"[{done+1}] (바닥) SKIP 처리 @ {ts[0]}")
                if reader.read_one(ts[0], geom=geom, log=log):
                    done += 1; fails = 0; continue
            log(f"SKIP 없음 — 캐릭터 완료 (읽음 {done}편)")
            break
    return done


if __name__ == "__main__":
    capture.connect()
    g = inp.window_geometry()
    n = scan_character(g)
    print(f"== 캐릭터 스캔 완료: {n}편 읽음 ==")
