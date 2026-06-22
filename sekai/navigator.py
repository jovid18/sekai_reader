"""그룹/캐릭터 네비게이션 (SPEC 로드맵 5).

process_group(): 캐릭터 선택 화면에서 시작 → 각 캐릭터 카드 진입 → scan_character → 뒤로 → 다음.
화면 전이는 매번 템플릿으로 검증(is_list_screen / is_char_select)해 폭주 방지.
"""
from __future__ import annotations
import time
from . import capture, recognize as rec, scanner
from . import input as inp

BACK = (60, 48)        # 좌상단 뒤로가기 화살표 (안드로이드 px)
CARD_Y = 300           # 카드 아트 위를 탭하는 y

# 카드 x중심. 실측: 6장 = 400~1760 균등(간격 272). 4장은 같은 영역에 균등 분포.
_X0, _X1 = 400, 1760


def card_centers(n: int) -> list[int]:
    if n == 1:
        return [(_X0 + _X1) // 2]
    return [round(_X0 + (_X1 - _X0) * i / (n - 1)) for i in range(n)]


def _back_to_char_select(geom, log) -> bool:
    for _ in range(2):
        inp.tap(*BACK, geom)
        time.sleep(1.2)
        if rec.is_char_select(capture.grab()):
            return True
    log("⚠️ 캐릭터 선택 화면 복귀 실패")
    return False


def process_group(n_chars: int, geom=None, log=print) -> int:
    """현재 그룹(캐릭터 선택 화면)의 모든 캐릭터를 순회하며 미열람 처리. 총 읽은 편수 반환."""
    geom = geom or inp.window_geometry()
    if not rec.is_char_select(capture.grab()):
        log("⚠️ 캐릭터 선택 화면이 아님 — 중단")
        return 0
    total = 0
    for i, cx in enumerate(card_centers(n_chars)):
        log(f"=== 캐릭터 {i+1}/{n_chars} (x={cx}) ===")
        inp.tap(cx, CARD_Y, geom)
        time.sleep(1.3)
        if not rec.is_list_screen(capture.grab()):
            log("  진입 실패(목록 아님) — 이 캐릭터 스킵")
            if not rec.is_char_select(capture.grab()):
                _back_to_char_select(geom, log)
            continue
        n = scanner.scan_character(geom, log)
        total += n
        log(f"  → {n}편 읽음")
        if not _back_to_char_select(geom, log):
            break
    log(f"=== 그룹 완료: 총 {total}편 ===")
    return total


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    capture.connect()
    process_group(n)
