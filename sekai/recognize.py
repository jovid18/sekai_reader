"""인식(눈→판단): 전부 로컬 OpenCV. 토큰 0.

- count_buttons(): 흰색 알약형 버튼(前編/後編) 개수. 목록 화면엔 많고 재생 화면엔 0.
- is_list_screen(): 에피소드 목록 화면인지(=스토리 종료 후 복귀 감지).
- find_skip(): 초록 SKIP 뱃지 전수 검출 → 미열람 버튼 좌표.
"""
from __future__ import annotations
import os
import numpy as np
import cv2

_HERE = os.path.dirname(__file__)
_TMPL_DIR = os.path.join(_HERE, "..", "assets", "templates")
_SKIP = cv2.imread(os.path.join(_TMPL_DIR, "skip_badge.png"))
_VOICE_NONE = cv2.imread(os.path.join(_TMPL_DIR, "voice_none.png"))
_LIST_BAR = cv2.imread(os.path.join(_TMPL_DIR, "list_bar.png"))
_CHAR_SELECT = cv2.imread(os.path.join(_TMPL_DIR, "char_select.png"))
_UNLOCK = cv2.imread(os.path.join(_TMPL_DIR, "unlock_dialog.png"))

# 버튼 탐색 영역(좌측 캐릭터·상단바·우측툴바 제외). 안드로이드 1920x1080 기준.
BTN_REGION = (440, 150, 1850, 1060)  # x0,y0,x1,y1


def button_boxes(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    """흰색 알약형 버튼 박스 [(x,y,w,h), ...] (안드로이드 px, 전체좌표)."""
    x0, y0, x1, y1 = BTN_REGION
    roi = img[y0:y1, x0:x1]
    white = cv2.inRange(roi, (225, 225, 225), (255, 255, 255))
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((5, 25), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(white, 8)
    boxes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if 110 < w < 240 and 45 < h < 85 and area > 4000:
            boxes.append((x + x0, y + y0, w, h))
    return boxes


def count_buttons(img: np.ndarray) -> int:
    return len(button_boxes(img))


def is_list_screen(img: np.ndarray, thr: float = 0.85) -> bool:
    """에피소드 목록 화면인지 — 상단 정렬바('デフォルト') 템플릿으로 판정.
    스크롤·잠김 여부와 무관하게 항상 떠 있어 흰버튼 개수보다 견고. 재생/다이얼로그에선 없음."""
    res = cv2.matchTemplate(img, _LIST_BAR, cv2.TM_CCOEFF_NORMED)
    return float(cv2.minMaxLoc(res)[1]) >= thr


def find_skip(img: np.ndarray, thr: float = 0.80) -> list[tuple[int, int, float]]:
    """초록 SKIP 뱃지 중심좌표 리스트 [(cx,cy,score), ...] (안드로이드 px)."""
    res = cv2.matchTemplate(img, _SKIP, cv2.TM_CCOEFF_NORMED)
    th, tw = _SKIP.shape[:2]
    pts = [(int(x), int(y), float(res[y, x])) for y, x in zip(*np.where(res >= thr))]
    pts.sort(key=lambda p: -p[2])
    keep: list[tuple[int, int, float]] = []
    for x, y, s in pts:
        if all(abs(x - kx) > 50 or abs(y - ky) > 50 for kx, ky, _ in keep):
            keep.append((x + tw // 2, y + th // 2, s))
    return keep


def is_unlock_dialog(img: np.ndarray, thr: float = 0.85) -> bool:
    """'「サイドストーリー○編」を解放しますか?' 해제(재화소모) 다이얼로그인지.
    前編 읽고 나면 잠긴 後編 해제를 권유하며 뜸 → 연타로 잘못 확정하면 보석 소모. 감지해 キャンセル해야 함."""
    res = cv2.matchTemplate(img, _UNLOCK, cv2.TM_CCOEFF_NORMED)
    return float(cv2.minMaxLoc(res)[1]) >= thr


def is_char_select(img: np.ndarray, thr: float = 0.85) -> bool:
    """캐릭터 선택 화면인지 — 하단 'キャラクターを選択してください' 텍스트로 판정."""
    res = cv2.matchTemplate(img, _CHAR_SELECT, cv2.TM_CCOEFF_NORMED)
    return float(cv2.minMaxLoc(res)[1]) >= thr


def find_voice_none(img: np.ndarray, thr: float = 0.85) -> tuple[int, int] | None:
    """보이스 다운로드 다이얼로그의 'ボイスなし' 버튼 중심좌표(있으면). 없으면 None."""
    res = cv2.matchTemplate(img, _VOICE_NONE, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < thr:
        return None
    th, tw = _VOICE_NONE.shape[:2]
    return (loc[0] + tw // 2, loc[1] + th // 2)


# SKIP 뱃지 중심 → 그 뱃지가 얹힌 前編/後編 버튼 중심까지의 고정 오프셋(안드로이드 px).
# 뱃지는 항상 버튼의 '우상단 모서리'에 붙으므로 좌하로 이동하면 버튼 위에 떨어진다(좌/우 칼럼 공통, 실측).
_SKIP_DX, _SKIP_DY = 84, 26


def skip_targets(img: np.ndarray, thr: float = 0.88) -> list[tuple[int, int]]:
    """미열람(SKIP) 버튼들의 클릭 좌표 [(cx,cy), ...] (안드로이드 px).
    SKIP 뱃지(초록)를 검출하고 고정 오프셋으로 해당 버튼 중심을 계산. button_boxes는
    썸네일/Lv배지 등 가짜 흰영역이 섞여 불안정하므로 쓰지 않는다."""
    return [(cx - _SKIP_DX, cy + _SKIP_DY) for cx, cy, _ in find_skip(img, thr)]


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        im = cv2.imread(path)
        print(f"{os.path.basename(path):28s} buttons={count_buttons(im):2d} "
              f"list={is_list_screen(im)} skips={len(find_skip(im))} "
              f"targets={skip_targets(im)}")
