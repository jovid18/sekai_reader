"""순회 오케스트레이션 (SPEC 로드맵 5).

scan_character(): 현재 캐릭터의 에피소드 목록을 맨 위부터 훑으며 SKIP(미열람)을 전부 읽어 제거.
- 목록은 길어 스크롤 필요. 스크롤은 macOS 드래그(input.swipe), 좌/우 2열 + 본인/他メンバー 2탭 구조.

### 2026-06-26 견고화 (흩어진 잔여 SKIP 버그 2개 수정)
이전 구현은 '스크롤해도 화면이 안 변하면 바닥'이라는 무이동 감지로 sweep을 끝냈는데:
  (1) BlueStacks에 스와이프가 **간헐적으로 안 먹히면** 두 프레임이 동일 → '바닥'으로 오판 →
      아래쪽 SKIP을 통째로 놓치고 조기 종료. (캐릭터마다 운에 따라 잔여가 흩어진 원인)
  (2) SAFE_MAX_Y=720 이 너무 보수적 → 목록 **하단** SKIP이 관성 오버슛으로 안전 band에 못 들어와
      영영 클릭되지 않음.
→ (1) 무이동 감지 폐기, **가장 긴 목록도 덮는 고정 스텝 수로 결정적으로 훑음**(바닥 지나면 no-op).
  (2) SAFE_MAX_Y 720→860 (실측: y=766·833 클릭도 정상 진입). 하단 SKIP을 그 위치에서 바로 클릭.
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

# 결정적 sweep 파라미터 — 무이동 감지 대신 '가장 긴 목록도 덮는 고정 횟수'.
TOP_SWIPES = 20     # 맨 위 복귀용 위-스와이프 횟수(무조건)
SWEEP_STEPS = 22    # 위→아래 훑기 스텝 수(무조건). 바닥을 지나면 추가 스크롤은 무해(no-op).

# SKIP 타겟 y가 이 값 이하면 그 위치에서 바로 클릭. 목록 하단 SKIP은 관성 오버슛으로
# 좁은 안전 band에 안 들어오므로, 충분히 큰 값으로 잡아 하단에서도 직접 클릭한다(실측: y=833 정상 진입).
SAFE_MAX_Y = 860


def _scroll_down(geom):
    inp.swipe(*_DOWN_FROM, *_DOWN_TO, steps=_DOWN_STEPS, hold_ms=_DOWN_HOLD, geom=geom)
    time.sleep(_SETTLE)


def _sig(img: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = rec.BTN_REGION
    g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (96, 64), interpolation=cv2.INTER_AREA).astype(np.float32)


def screens_equal(a: np.ndarray, b: np.ndarray, thr: float = 6.0) -> bool:
    """두 프레임이 사실상 동일한가(실측: 실제 스크롤 시 MSE>1000, 동일 시 ~0)."""
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


def scroll_to_top(geom, log=print, n: int = TOP_SWIPES) -> np.ndarray:
    """맨 위로 복귀 — 무이동 감지에 의존하지 않고 충분한 횟수만큼 위로 스와이프한다.
    이미 맨 위면 추가 스와이프는 무해(no-op). 단일 스와이프 불발에 강인."""
    for _ in range(n):
        inp.swipe(*_UP_FROM, *_UP_TO, geom=geom)
        time.sleep(0.45)
    return grab_settled()


def _read_clickable_here(geom, log, st) -> None:
    """현재 뷰의 클릭가능 SKIP을 위에서부터 모두 읽는다(읽을 때마다 재캡처). 실패 시 중단."""
    for _ in range(12):
        img = grab_settled()
        ts = sorted(rec.skip_targets(img), key=lambda t: t[1])
        clickable = [t for t in ts if t[1] <= SAFE_MAX_Y]
        if not clickable:
            return
        tgt = clickable[0]
        st['n'] += 1
        log(f"[{st['n']}] SKIP 처리 @ {tgt}")
        if reader.read_one(tgt, geom=geom, log=log):
            st['read'] += 1
        else:
            st['fail'] += 1
            log(f"  ⚠️ read_one 실패 (누적 {st['fail']}) @ {tgt}")
            return


def scan_character(geom=None, log=print, max_episodes: int = 120) -> int:
    """현재 캐릭터의 SKIP을 전부 읽어 제거. 읽은 편수 반환.

    결정적 sweep: 맨 위에서 고정 스텝 수(SWEEP_STEPS)만큼 아래로 훑으며 각 뷰의 클릭가능 SKIP을
    모두 읽는다. 무이동을 '바닥'으로 오판해 조기 종료하던 버그를 제거(스와이프 간헐 불발에 강인).
    """
    geom = geom or inp.window_geometry()
    st = {'n': 0, 'read': 0, 'fail': 0}
    scroll_to_top(geom, log)
    for _ in range(SWEEP_STEPS):
        _read_clickable_here(geom, log, st)
        if st['fail'] >= 4:
            log(f"⚠️ 누적 실패 {st['fail']} — 중단 (미처리 SKIP 남았을 수 있음)")
            break
        _scroll_down(geom)
    _read_clickable_here(geom, log, st)   # 마지막 뷰
    log(f"완료 — {st['read']}편 읽음")
    return st['read']


def count_remaining(geom=None) -> int:
    """현재 캐릭터를 결정적으로 전체 sweep하며 동시 검출된 SKIP 최대수 반환(검증용, 조기종료 없음)."""
    geom = geom or inp.window_geometry()
    scroll_to_top(geom, log=lambda *a: None)
    mx = 0
    for _ in range(SWEEP_STEPS):
        img = grab_settled()
        mx = max(mx, len(rec.find_skip(img, 0.80)))
        _scroll_down(geom)
    img = grab_settled()
    return max(mx, len(rec.find_skip(img, 0.80)))


if __name__ == "__main__":
    capture.connect()
    g = inp.window_geometry()
    n = scan_character(g)
    rem = count_remaining(g)
    print(f"== 캐릭터 스캔 완료: {n}편 읽음, 검증 잔여 SKIP {rem} ==")
