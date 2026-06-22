"""한 에피소드 자동 완독 루프 (SPEC 로드맵 4).

흐름: SKIP 버튼 클릭 → (보이스 다이얼로그면 'ボイスなし' 클릭) → 화면 중앙 연타로 진행
      → 목록 화면으로 복귀 감지되면 종료.

연타 지점은 화면 중앙(960,540): 재생 화면에선 '다음 대사'로 진행, 목록 화면에선
두 칼럼 사이 빈 공간이라 눌려도 무해 → 오작동 위험 낮음. 종료는 is_list_screen으로 감지.
"""
from __future__ import annotations
import time
from . import capture, recognize as rec
from . import input as inp

# 연타 지점: 화면 우측 가장자리(안드로이드 px). 중앙을 쓰면 前編 종료 후 뜨는
# '後編 해제?' 프롬프트의 중앙 버튼을 잘못 눌러 재화를 소모할 수 있어 우측으로 옮김.
# 우상단 ・・・(메뉴)·우하단 ♪ 와도 겹치지 않고, 목록 화면에선 버튼 영역 밖(여백)이라 안전.
TAP_POINT = (1820, 560)
# 게임이 탭을 '다음 대사'로 확실히 인식하는 한계가 ~85ms/탭(더 빠르면 일부 무시됨)이라 그게 실질 상한.
# 캡처(screencap ~0.7s)를 덜 하려고 버스트를 크게 잡아 캡처당 여러 탭을 묶는다.
BURST = 20                   # 캡처 1회당 연타 횟수
BURST_GAP_MS = 85           # 버스트 내 클릭 간격(ms)
UNLOCK_CANCEL = (760, 987)   # 해제 다이얼로그의 キャンセル 버튼


def read_one(target: tuple[int, int],
             geom: tuple[int, int, int, int] | None = None,
             max_taps: int = 900, log=print) -> bool:
    """target(미열람 버튼 중심) 1편을 끝까지 읽고 목록 복귀하면 True."""
    geom = geom or inp.window_geometry()

    # 1) 에피소드 진입
    log(f"진입 클릭 {target}")
    inp.tap(*target, geom)

    # 2) 보이스 다이얼로그 처리 (뜨면 ボイスなし, 안 뜨고 바로 재생되면 통과)
    for _ in range(12):
        time.sleep(0.35)
        img = capture.grab()
        vn = rec.find_voice_none(img)
        if vn:
            log(f"ボイスなし 클릭 {vn}")
            inp.tap(*vn, geom)
            time.sleep(0.6)
            break
        if not rec.is_list_screen(img):
            log("다이얼로그 없이 재생 진입")
            break
    else:
        log("⚠️ 다이얼로그/재생 진입 실패 (목록 그대로) — 클릭이 빗나갔을 수 있음")
        return False

    # 3) 우측 연타로 끝까지 → 목록 복귀 감지 (+ 해제 다이얼로그는 キャンセル)
    taps = 0
    list_seen = 0
    while taps < max_taps:
        img = capture.grab()
        if rec.is_list_screen(img):
            list_seen += 1
            if list_seen >= 2:        # 목록 안정적으로 2회 연속 → 종료 확정
                log(f"목록 복귀 감지 (연타 {taps}회). 완료.")
                return True
            time.sleep(0.25)
            continue
        list_seen = 0
        if rec.is_unlock_dialog(img):
            log("後編 해제 다이얼로그 감지 → キャンセル (재화 보호)")
            inp.tap(*UNLOCK_CANCEL, geom)
            time.sleep(0.8)
            continue
        inp.tap_burst(*TAP_POINT, n=BURST, gap_ms=BURST_GAP_MS, geom=geom)
        taps += BURST

    log(f"⚠️ max_taps({max_taps}) 도달 — 종료 감지 실패")
    return False


if __name__ == "__main__":
    capture.connect()
    img = capture.grab()
    targets = rec.skip_targets(img)
    if not targets:
        print("현재 화면에 SKIP(미열람) 없음.")
    else:
        print(f"SKIP 타겟 {len(targets)}개: {targets} → 첫 번째 1편 읽기 시작")
        read_one(targets[0])
