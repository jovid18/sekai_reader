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

CENTER = (960, 540)          # 연타 지점 (안드로이드 px)
TAP_INTERVAL = 0.18          # 연타 간격(초)
VOICE_NONE_FALLBACK = (940, 970)


def read_one(target: tuple[int, int],
             geom: tuple[int, int, int, int] | None = None,
             max_taps: int = 500, log=print) -> bool:
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

    # 3) 중앙 연타로 끝까지 → 목록 복귀 감지
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
        inp.tap(*CENTER, geom)
        taps += 1
        time.sleep(TAP_INTERVAL)

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
