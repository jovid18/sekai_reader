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

# 카드 x중심 (안드로이드 px, 실측). 개수마다 배치가 달라 개수별로 박아둠.
_CARD_CENTERS = {
    6: [400, 672, 944, 1216, 1488, 1760],   # VIRTUAL SINGER
    4: [430, 790, 1150, 1510],              # 나머지 그룹
}

# 좌측 그룹 탭 (안드로이드 px). (이름, 탭y, 캐릭터수). 전부 실측 확인.
GROUP_TAB_X = 85
GROUPS = [
    ("VIRTUAL SINGER", 195, 6),
    ("Leo/need", 325, 4),
    ("MORE MORE JUMP!", 450, 4),
    ("Vivid BAD SQUAD", 570, 4),
    ("ワンダーランズ×ショウタイム", 695, 4),
    ("25時、ナイトコードで", 820, 4),
]


def card_centers(n: int) -> list[int]:
    return _CARD_CENTERS.get(n) or [round(430 + (1510 - 430) * i / max(1, n - 1)) for i in range(n)]


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


def select_group(tab_y: int, geom, log=print) -> bool:
    """좌측 그룹 탭을 눌러 그 그룹의 캐릭터 선택 화면으로 전환."""
    inp.tap(GROUP_TAB_X, tab_y, geom)
    time.sleep(1.5)
    return rec.is_char_select(capture.grab())


def process_all(geom=None, log=print) -> int:
    """6개 그룹 × 전 캐릭터의 미열람 사이드 스토리를 전부 자동 처리. 캐릭터 선택 화면에서 시작.
    총 읽은 편수 반환."""
    geom = geom or inp.window_geometry()
    if not rec.is_char_select(capture.grab()):
        log("⚠️ 캐릭터 선택 화면에서 시작해야 함 — 중단")
        return 0
    grand = 0
    for name, tab_y, n_chars in GROUPS:
        log(f"\n########## 그룹: {name} ({n_chars}명) ##########")
        if not select_group(tab_y, geom, log):
            log(f"⚠️ 그룹 '{name}' 선택 실패 — 스킵")
            continue
        n = process_group(n_chars, geom, log)
        grand += n
        log(f"########## '{name}' 완료: {n}편 (누적 {grand}편) ##########")
    log(f"\n========== 전체 완료: 총 {grand}편 ==========")
    return grand


if __name__ == "__main__":
    import sys
    capture.connect()
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        process_all()
    else:
        n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
        process_group(n)
