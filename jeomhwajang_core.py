"""
각궁 점화장 제작도면 생성 코어
- 양문 여닫이 장, 아래 조절부 칸(고정판), 몸체 사개(천판·지판 ↔ 옆판)
- 겉판 + 단열재 + 면상필름 + 삼나무 속판 샌드위치, 문은 단열 플러그 + 가스켓으로 밀폐
- 부린활 n장을 깊이 방향으로 나란히 거는 거치대(삼각 받침 / 둥근 막대 / 줌걸이)
출력: PDF(A3 4장), DXF(부재 전개 1:1), CSV(재단표)
  python jeomhwajang_core.py      → output 폴더에 기본값으로 생성
좌표: x 왼→오(정면에서 볼 때), y 앞→뒤, z 아래→위, 단위 mm
"""
import os
import csv
import math
import datetime
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Polygon, Rectangle, Circle
import ezdxf


def _setup_font():
    names = {f.name for f in fm.fontManager.ttflist}
    for cand in ("Malgun Gothic", "맑은 고딕", "NanumGothic", "Noto Sans CJK KR", "Noto Sans CJK JP", "AppleGothic"):
        if cand in names:
            plt.rcParams["font.family"] = cand
            return cand
    for p in (r"C:\Windows\Fonts\malgun.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            return p
    # 함께 넣은 나눔고딕(OFL) — 웹(브라우저) 버전이나 한글 글꼴이 없는 PC
    import sys as _sys
    base = getattr(_sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    found = None
    for nm in ("NanumGothic-Regular.ttf", "NanumGothic-Bold.ttf"):
        p = os.path.join(base, "assets", "fonts", nm)
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            found = found or p
    if found:   # 나눔고딕에 없는 기호(①·℃·−)는 DejaVu Sans로 대신 그림
        plt.rcParams["font.family"] = [fm.FontProperties(fname=found).get_name(), "DejaVu Sans"]
    return found


_setup_font()
plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------- 기본값
PARAM = dict(
    # 본체
    W=1000.0, H=800.0, D=320.0,      # 외형 가로·높이·깊이
    t=18.0,                         # 겉판 두께(옆판·천판·지판·뒷판·아래 앞판)
    foot_h=30.0, foot_w=60.0,       # 발 높이·크기(4개)
    pin_pitch=40.0,                 # 사개 손 간격(목표)
    dado=6.0,                       # 뒷판·아래 앞판 홈 깊이
    # 단열·밀폐
    t_ins=10.0,                     # 단열재 두께
    t_in=9.0,                       # 속판(삼나무) 두께
    frame_d=20.0,                   # 문틀 띠 깊이(단열층 앞 원목 띠)
    gasket="1",                     # 가스켓 사용 1 / 0
    gasket_w=9.0, gasket_h=6.0,     # 가스켓 폭·두께
    gap=2.0,                        # 문 둘레 틈
    plug_gap=3.0,                   # 문 단열 플러그 둘레 틈
    rebate=12.0,                    # 양문 맞닿는 턱 너비
    # 문
    door_type="double",             # double 양문 여닫이 | bandaji 반닫이(문판이 앞으로 젖혀 열림)
    door_h=350.0,                   # 문 높이(천판 아래에서 아래로)
    bj_cleat=45.0,                  # 반닫이 문판 양끝 마구리 폭(0이면 통판)
    bj_hinges=3,                    # 반닫이 경첩 수(문판 아래 끝)
    bj_stays=0,                     # 반닫이 지지대 수(0이면 바닥에 닿을 때까지 열림, 1 이상이면 90°에서 멈춤)
    t_door=18.0,                    # 문 겉판 두께
    hinges=2,                       # 문 한 짝당 경첩 수
    mag_n=1,                        # 문 한 짝당 자석 캐치 수(1: 위, 2: 위·아래)
    mag_d=12.0, mag_off=60.0,       # 자석 지름, 가운데에서 떨어진 거리
    # 하부 공간·선반
    lower_h=120.0,                  # 하부 공간 안높이(속 바닥 → 선반 아랫면)
    shelf_t=18.0,                   # 선반 두께
    cleat=20.0,                     # 선반받이 각재
    vent_w=10.0, vent_pitch=30.0,   # 통풍 슬롯 폭·간격
    # 온도조절기·전원
    ctl_side="L",                   # 온도조절기·리셉터클 쪽 L/R
    thermo_w=152.0, thermo_h=72.0,  # 온습도 조절기 몸체 타공
    bezel_w=160.0, bezel_h=80.0,    # 조절기 앞 테두리(XM-18 160×80)
    ctl_depth=89.0,                 # 조절기 깊이(테두리 포함)
    thermo_x=60.0,                  # 옆판 바깥 → 앞 테두리 가장자리
    recp_w=32.0, recp_h=22.0,       # 전원 리셉터클(IEC 인렛, 수평 배치) 몸체 타공
    recp_pitch=40.0, recp_hole=3.2, # 나사 구멍 좌우 간격·지름
    recp_x=60.0,                    # 옆판 바깥 → 타공 가장자리(뒤에서 볼 때 같은 쪽)
    set_temp=30.0,                  # 설정 온도 ℃
    # 열원
    heat="ptc",                     # ptc PTC 히터(하부) | film 면상필름
    film_faces="뒤,아래,좌,우",
    film_w=800.0, film_margin=20.0, film_wpm2=200.0,
    ptc_w=230.0, ptc_d=150.0, ptc_h=70.0, ptc_watt=200.0,  # PTC 히터(하부 바닥 가운데)
    # 거치대
    rack="1",                       # 1 삼각 받침 2개 / 2 둥근 막대 2개 / 3 줌걸이 1개
    rack_drop=85.0,                 # 속 천장 → 거치대 윗면
    rack_gap=260.0,                 # 받침·막대 중심 간격(1·2형)
    rack_back=10.0,                 # 뒷속판 → 첫 활
    rack_front=5.0,                 # 거치대 앞끝 → 문 안쪽 면
    rack_r=8.0,                     # 활 닿는 부분 라운드 R
    r1_w=40.0, r1_h=90.0, r1_tip=30.0, r1_lip=12.0,
    r2_d=25.0,
    r3_arm=40.0, r3_cap_w=120.0, r3_cap_h=30.0,
    # 활
    n_bows=4, bow_pitch=50.0,
    bow_open_span=880.0, bow_open_h=300.0,
    bow_ring_w=560.0, bow_ring_h=500.0,
    bow_limb=25.0, clear=20.0,
)

FACE_NAMES = ("뒤", "위", "아래", "좌", "우")
INT_KEYS = ("hinges", "n_bows", "mag_n", "bj_hinges", "bj_stays")
STR_KEYS = ("heat", "film_faces", "rack", "gasket", "ctl_side", "door_type")

MAT = {
    "pine": ("레드파인", "#e8cc98"),
    "cedar": ("삼나무", "#f5e6c8"),
    "ins": ("단열재", "#f2b8c6"),
    "ply": ("집성목", "#c9a46a"),
    "steel": ("철물", "#555555"),
    "film": ("면상필름", "#e03030"),
    "gasket": ("가스켓", "#222222"),
    "ptc": ("PTC 히터", "#9aa3ad"),
}


def P():
    return PARAM


# ---------------------------------------------------------------- 부재 모델
def _box(name, x0, x1, y0, y1, z0, z1, mat, keys=(), tags=(), bom=None, dev=None, **kw):
    d = dict(name=name, b=(min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)),
             mat=mat, keys=set(keys), tags=set(tags), bom=bom, dev=dev)
    d.update(kw)
    return d


def pins(L, pitch):
    """사개 손 경계: 홀수 개 구간"""
    n = max(3, int(round(L / max(pitch, 5))))
    if n % 2 == 0:
        n += 1
    return [L * i / n for i in range(n + 1)]


def notched_board(length, width, bnds, t, notch_odd):
    """양 끝(길이 방향 0, length)에 사개 홈을 낸 판의 전개 외곽"""
    segs = list(zip(bnds[:-1], bnds[1:]))
    cut = [(i % 2 == 1) == notch_odd for i in range(len(segs))]
    pts = []
    for (a, b), c in zip(segs, cut):
        x = t if c else 0.0
        pts += [(x, a), (x, b)]
    for (a, b), c in reversed(list(zip(segs, cut))):
        x = length - t if c else length
        pts += [(x, b), (x, a)]
    out = []
    for q in pts:
        if not out or (abs(out[-1][0] - q[0]) > 1e-9 or abs(out[-1][1] - q[1]) > 1e-9):
            out.append(q)
    return out


def rect(w, h):
    return [(0, 0), (w, 0), (w, h), (0, h)]


def is_bandaji():
    return str(P().get("door_type", "double")) == "bandaji"


def gasket_on():
    return str(P()["gasket"]) in ("1", "True", "true", "on")


def derive():
    """주요 기준 높이·위치"""
    p = P()
    t, ti, tl = p["t"], p["t_ins"], p["t_in"]
    W, H, D = p["W"], p["H"], p["D"]
    f, td, g = p["foot_h"], p["t_door"], p["gap"]
    s = ti + tl
    gk = p["gasket_h"] * 0.5 if gasket_on() else 0.0      # 가스켓 눌린 두께
    yfront = td + gk                                       # 문틀 띠 앞면
    y0i = yfront + p["frame_d"]                            # 단열층 시작
    zt1 = H - t                                            # 천판 아랫면
    zb1 = f + t                                            # 지판 윗면
    dz1 = zt1 - g
    dz0 = dz1 - p["door_h"]
    d = dict(
        s=s, gk=gk, yfront=yfront, y0i=y0i, zt1=zt1, zb1=zb1,
        dz0=dz0, dz1=dz1, rail0=dz0 - s, rail1=dz0 + s,      # 문 아래 문틀 띠
        cx0=t + s, cx1=W - t - s,
        cy0=td + s, cy1=D - t - s,
        cz0=zb1 + s, cz1=zt1 - s,
        xm=W / 2,
    )
    d["zs0"] = d["cz0"] + p["lower_h"]                     # 선반 아랫면
    d["zs1"] = d["zs0"] + p["shelf_t"]                     # 선반 윗면(활 칸 바닥)
    d["cw"], d["cd"], d["ch"] = d["cx1"] - d["cx0"], d["cy1"] - d["cy0"], d["cz1"] - d["zs1"]
    d["rack_top"] = d["cz1"] - p["rack_drop"]
    d["rack_len"] = d["cd"] - p["rack_front"]
    d["door_z"] = (dz0, dz1)
    d["open_h"] = d["cz1"] - d["rail1"]                    # 문 열린 높이(문틀 띠 사이)
    left = p["ctl_side"] != "R"
    tw, th = p["thermo_w"], p["thermo_h"]
    bw = max(p["bezel_w"], tw)
    tx = (p["thermo_x"] + bw / 2) if left else (W - p["thermo_x"] - bw / 2)
    d["thermo"] = (tx, (d["cz0"] + d["zs0"]) / 2, tw, th)
    rx = (p["recp_x"] + p["recp_w"] / 2) if left else (W - p["recp_x"] - p["recp_w"] / 2)
    d["recp"] = (rx, (d["cz0"] + d["zs0"]) / 2, p["recp_w"], p["recp_h"])
    return d


def faces():
    return [f.strip() for f in str(P()["film_faces"]).replace(" ", ",").split(",") if f.strip() in FACE_NAMES]


def shelf_slots(sw, sd):
    """선반 통풍 슬롯(선반 좌표: 가로 sw, 깊이 sd) → [(x0, y0, w, h)]"""
    p = P()
    m = 40.0
    vw, vp = p["vent_w"], max(p["vent_pitch"], p["vent_w"] + 5)
    n = int((sw - 2 * m - vw) // vp) + 1
    if n < 1 or sd - 2 * m <= 10:
        return []
    x0 = (sw - (vw + (n - 1) * vp)) / 2
    return [(x0 + i * vp, m, vw, sd - 2 * m) for i in range(n)]


def build():
    """모든 부재 목록"""
    p, d = P(), derive()
    W, H, D = p["W"], p["H"], p["D"]
    t, ti, tl, s = p["t"], p["t_ins"], p["t_in"], d["s"]
    f, td, g = p["foot_h"], p["t_door"], p["gap"]
    xm, yf, y0i = d["xm"], d["yfront"], d["y0i"]
    zt1, zb1 = d["zt1"], d["zb1"]
    dz0, dz1 = d["door_z"]
    yb = D - t
    parts = []
    A = parts.append

    # --- 몸체 겉판(사개: 천판·지판 ↔ 옆판)
    bn = pins(D, p["pin_pitch"])
    side_len = H - f
    A(_box("천판", 0, W, 0, D, zt1, H, "pine", keys={"W", "D", "t", "pin_pitch"}, tags={"shell"},
           bom=("천판", "pine", W, D, t, "사개"), dev=notched_board(W, D, bn, t, True)))
    A(_box("지판", 0, W, 0, D, f, zb1, "pine", keys={"W", "D", "t", "pin_pitch"}, tags={"shell"},
           bom=("지판", "pine", W, D, t, "사개"), dev=notched_board(W, D, bn, t, True)))
    for nm, x0 in (("옆판(좌)", 0), ("옆판(우)", W - t)):
        A(_box(nm, x0, x0 + t, 0, D, f, H, "pine", keys={"H", "D", "t", "pin_pitch", "foot_h"}, tags={"shell"},
               bom=("옆판", "pine", side_len, D, t, "사개"), dev=notched_board(side_len, D, bn, t, False)))
    rx, rz, rw, rh = d["recp"]
    A(_box("뒷판", t, W - t, yb, D, zb1, zt1, "pine", keys={"W", "H", "t", "recp_w", "recp_h", "recp_x", "ctl_side"},
           tags={"shell", "back"}, holes=[("recp", rx, rz, rw, rh)],
           bom=("뒷판", "pine", W - 2 * t + 2 * p["dado"], zt1 - zb1 + 2 * p["dado"], t, "홈 끼움, 리셉터클 타공(앞에서 본 위치)"),
           dev=rect(W - 2 * t + 2 * p["dado"], zt1 - zb1 + 2 * p["dado"]),
           dev_holes=[("recp", rx - (t - p["dado"]), rz - (zb1 - p["dado"]), rw, rh)]))
    tx, tz, tw, th = d["thermo"]
    A(_box("아래 앞판", t, W - t, 0, t, zb1, dz0 - g, "pine",
           keys={"door_h", "thermo_w", "thermo_h", "thermo_x", "ctl_side", "lower_h"}, tags={"shell", "front"},
           holes=[("thermo", tx, tz, tw, th)],
           bom=("아래 앞판", "pine", W - 2 * t + 2 * p["dado"], dz0 - g - zb1 + p["dado"], t, "홈 끼움, 온도조절기 타공"),
           dev=rect(W - 2 * t + 2 * p["dado"], dz0 - g - zb1 + p["dado"]),
           dev_holes=[("thermo", tx - (t - p["dado"]), tz - (zb1 - p["dado"]), tw, th)]))
    fw = p["foot_w"]
    if f > 0:
        for x0, y0 in ((10, 10), (W - 10 - fw, 10), (10, D - 10 - fw), (W - 10 - fw, D - 10 - fw)):
            A(_box("발", x0, x0 + fw, y0, y0 + fw, 0, f, "pine", keys={"foot_h", "foot_w"}, tags={"foot"},
                   bom=("발", "pine", fw, fw, f, "")))

    # --- 문틀 띠(원목): 단열층 앞 둘레, 문이 닿는 면
    fk = {"frame_d", "gasket", "gasket_h"}
    fd = p["frame_d"]
    A(_box("문틀 띠(위)", t, W - t, yf, y0i, zt1 - s, zt1, "pine", keys=fk, tags={"frame"},
           bom=("문틀 띠 위", "pine", W - 2 * t, fd, s, "")))
    A(_box("문틀 띠(아래·문)", t + s, W - t - s, yf, y0i, d["rail0"], d["rail1"], "pine", keys=fk | {"door_h"}, tags={"frame"},
           bom=("문틀 띠 문 아래", "pine", W - 2 * t - 2 * s, fd, 2 * s, "")))
    A(_box("문틀 띠(바닥)", t + s, W - t - s, yf, y0i, zb1, zb1 + s, "pine", keys=fk, tags={"frame"},
           bom=("문틀 띠 바닥", "pine", W - 2 * t - 2 * s, fd, s, "")))
    for nm, x0 in (("문틀 띠(좌)", t), ("문틀 띠(우)", W - t - s)):
        A(_box(nm, x0, x0 + s, yf, y0i, zb1, zt1 - s, "pine", keys=fk, tags={"frame"},
               bom=("문틀 띠 옆", "pine", zt1 - s - zb1, fd, s, "")))

    # --- 단열재 + 속판 (위·아래 전체 폭, 옆은 그 사이, 뒤·앞(아래)은 가장 안쪽)
    a0, a1 = t + ti, W - t - ti
    b1 = yb - ti
    A(_box("단열재(위)", t, W - t, y0i, yb, zt1 - ti, zt1, "ins", keys={"t_ins"}, tags={"ins"},
           bom=("단열재 위", "ins", W - 2 * t, yb - y0i, ti, "")))
    A(_box("단열재(아래)", t, W - t, y0i, yb, zb1, zb1 + ti, "ins", keys={"t_ins"}, tags={"ins"},
           bom=("단열재 아래", "ins", W - 2 * t, yb - y0i, ti, "")))
    for nm, x0 in (("단열재(좌)", t), ("단열재(우)", W - t - ti)):
        A(_box(nm, x0, x0 + ti, y0i, yb, zb1 + ti, zt1 - ti, "ins", keys={"t_ins"}, tags={"ins"},
               bom=("단열재 옆", "ins", zt1 - zb1 - 2 * ti, yb - y0i, ti, "")))
    A(_box("단열재(뒤)", a0, a1, b1, yb, zb1 + ti, zt1 - ti, "ins", keys={"t_ins"}, tags={"ins"},
           bom=("단열재 뒤", "ins", a1 - a0, zt1 - zb1 - 2 * ti, ti, "리셉터클 자리 40×50 따냄")))
    A(_box("속판(위)", a0, a1, y0i, b1, zt1 - s, zt1 - ti, "cedar", keys={"t_in"}, tags={"lining"},
           bom=("속판 위", "cedar", a1 - a0, b1 - y0i, tl, "")))
    A(_box("속판(아래)", a0, a1, y0i, b1, zb1 + ti, zb1 + s, "cedar", keys={"t_in"}, tags={"lining"},
           bom=("속판 아래", "cedar", a1 - a0, b1 - y0i, tl, "")))
    for nm, x0 in (("속판(좌)", a0), ("속판(우)", a1 - tl)):
        A(_box(nm, x0, x0 + tl, y0i, b1, zb1 + s, zt1 - s, "cedar", keys={"t_in"}, tags={"lining"},
               bom=("속판 옆", "cedar", zt1 - zb1 - 2 * s, b1 - y0i, tl, "")))
    A(_box("속판(뒤)", a0 + tl, a1 - tl, b1 - tl, b1, zb1 + s, zt1 - s, "cedar", keys={"t_in"}, tags={"lining"},
           bom=("속판 뒤", "cedar", a1 - a0 - 2 * tl, zt1 - zb1 - 2 * s, tl, "리셉터클 자리 40×50 따냄")))
    # 아래 앞(고정판 뒤): 문틀 띠 사이, 바닥 띠 위 ~ 문 아래 띠 밑
    lz0, lz1 = zb1 + s, d["rail0"]
    A(_box("단열재(아래 앞)", t + s, W - t - s, y0i - s, y0i - tl, lz0, lz1, "ins", keys={"t_ins"}, tags={"ins", "lowfront"},
           bom=("단열재 아래 앞", "ins", W - 2 * t - 2 * s, lz1 - lz0, ti, "온도조절기 자리 따냄")))
    A(_box("속판(아래 앞)", t + s, W - t - s, y0i - tl, y0i, lz0, lz1, "cedar", keys={"t_in"}, tags={"lining", "lowfront"},
           bom=("속판 아래 앞", "cedar", W - 2 * t - 2 * s, lz1 - lz0, tl, "온도조절기 자리 따냄")))

    # 조절기(테두리 + 몸체), 타공은 3D용으로 단열재·속판에도
    tx, tz, tw, th = d["thermo"]
    bw, bh = max(p["bezel_w"], tw), max(p["bezel_h"], th)
    A(_box("온습도 조절기 테두리", tx - bw / 2, tx + bw / 2, -10, 0, tz - bh / 2, tz + bh / 2, "steel",
           tags={"ctl"}, keys={"bezel_w", "bezel_h", "thermo_x", "ctl_side"}))
    A(_box("온습도 조절기", tx - tw / 2, tx + tw / 2, 0, p["ctl_depth"] - 10, tz - th / 2, tz + th / 2, "steel",
           tags={"ctl"}, keys={"thermo_w", "thermo_h", "ctl_depth", "ctl_side"}))
    for q in parts:
        if "lowfront" in q["tags"] or q["name"] == "아래 앞판":
            q["holes3d"] = [("x", tx, tz, tw, th)]
        if q["name"] in ("단열재(뒤)", "속판(뒤)"):
            q["holes3d"] = [("x", rx, rz, 40.0, 50.0)]
        if q["name"] == "뒷판":
            q["holes3d"] = [("x", rx, rz, rw, rh)]

    # --- 가스켓(선택): 문틀 띠 앞면, 문 겉판 뒷면에 눌림
    if gasket_on():
        gw, gk = p["gasket_w"], d["gk"]
        gkeys = {"gasket", "gasket_w", "gasket_h"}
        A(_box("가스켓(위)", t, W - t, td, yf, zt1 - s / 2 - gw / 2, zt1 - s / 2 + gw / 2, "gasket", tags={"gasket"}, keys=gkeys))
        A(_box("가스켓(아래)", t + s, W - t - s, td, yf, dz0 + s / 2 - gw / 2, dz0 + s / 2 + gw / 2, "gasket", tags={"gasket"}, keys=gkeys))
        for x in (t + s / 2, W - t - s / 2):
            A(_box("가스켓(옆)", x - gw / 2, x + gw / 2, td, yf, dz0, zt1, "gasket", tags={"gasket"}, keys=gkeys))

    doorh = dz1 - dz0
    pg = p["plug_gap"]
    pz0, pz1 = d["rail1"] + pg, d["cz1"] - pg
    md = p["mag_d"]
    if is_bandaji():
        # --- 반닫이: 문판 한 장(양끝 마구리), 아래 끝 경첩으로 앞으로 젖혀 엶, 뒤에 단열 플러그 한 장
        dk = {"t_door", "gap", "door_h", "door_type", "bj_cleat"}
        x0d, x1d = t + g, W - t - g
        cw = max(p["bj_cleat"], 0.0)
        oB = [(x0d, 0), (x1d, 0), (x1d, td), (x0d, td)]
        if cw > 0:
            A(_box("문판", x0d + cw, x1d - cw, 0, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorB", "front", "noedge"}, oplan=oB,
                   bom=("문판(가운데)", "pine", x1d - x0d - 2 * cw + 2 * 10, doorh, td, "가로결, 양끝 촉 10"),
                   dev=rect(x1d - x0d, doorh), dev_cleat=cw))
            for nm, a_ in (("마구리(왼)", x0d), ("마구리(오른)", x1d - cw)):
                A(_box(nm, a_, a_ + cw, 0, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorB", "noedge"},
                       bom=("문판 마구리", "pine", doorh, cw, td, "세로결, 촉홈 10")))
        else:
            A(_box("문판", x0d, x1d, 0, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorB", "front", "noedge"}, oplan=oB,
                   bom=("문판(통판)", "pine", x1d - x0d, doorh, td, "가로결"), dev=rect(x1d - x0d, doorh)))
        tg = {"door", "doorB", "plug"}
        A(_box("문 단열재", d["cx0"] + pg, d["cx1"] - pg, td, td + ti, pz0, pz1, "ins", keys={"t_ins", "plug_gap"}, tags=tg,
               bom=("문 단열재", "ins", d["cx1"] - d["cx0"] - 2 * pg, pz1 - pz0, ti, "플러그")))
        A(_box("문 속판", d["cx0"] + pg, d["cx1"] - pg, td + ti, td + s, pz0, pz1, "cedar", keys={"t_in", "plug_gap"}, tags=tg,
               bom=("문 속판", "cedar", d["cx1"] - d["cx0"] - 2 * pg, pz1 - pz0, tl, "플러그")))
        # 자석: 위 문틀 띠, 가운데 좌우 + (2개면) 양끝 쪽
        mx = [xm - p["mag_off"], xm + p["mag_off"]]
        if int(p["mag_n"]) >= 2:
            mx += [d["cx0"] + 80, d["cx1"] - 80]
        for xc in mx:
            zc = zt1 - s / 2
            A(_box("자석 캐치", xc - md / 2, xc + md / 2, yf, yf + 6, zc - md / 2, zc + md / 2, "steel",
                   keys={"mag_n", "mag_d", "mag_off"}, tags={"mag"}, shape="disc"))
        # 가로 원목 손잡이(위 가운데)
        A(_box("원목 손잡이", xm - 60, xm + 60, -22, 0, dz1 - 80, dz1 - 60, "ply", tags={"door", "doorB", "handle"},
               keys={"door_h", "door_type"}))
        hw = []
        nh = max(int(p["bj_hinges"]), 1)
        for k in range(nh):
            xc = x0d + 80 + (x1d - x0d - 160) * (k / (nh - 1) if nh > 1 else 0.5)
            hw.append(("경첩B", xc, dz0))
        d["hardware"] = hw
        d["bj_angle"], d["bj_contact"] = bj_open(d)
    else:
        r = p["rebate"]
        hd = td / 2
        dk = {"t_door", "gap", "rebate", "door_h"}
        oL = [(t + g, 0), (xm - g / 2, 0), (xm - g / 2, hd), (xm + r, hd), (xm + r, td), (t + g, td)]
        oR = [(xm + g / 2, 0), (W - t - g, 0), (W - t - g, td), (xm + r + g, td), (xm + r + g, hd), (xm + g / 2, hd)]
        dw_L, dw_R = xm + r - (t + g), (W - t - g) - (xm + g / 2)
        A(_box("왼문 겉판", t + g, xm - g / 2, 0, hd, dz0, dz1, "pine", keys=dk, tags={"door", "doorL", "front", "noedge"}, oplan=oL,
               bom=("문 겉판(왼)", "pine", doorh, dw_L, td, f"오른쪽 끝 뒤쪽 반 턱 {r:g}×{hd:g}"), dev=rect(dw_L, doorh)))
        A(_box("왼문 겉판(턱)", t + g, xm + r, hd, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorL", "noedge"}))
        A(_box("오른문 겉판", xm + g / 2, W - t - g, 0, hd, dz0, dz1, "pine", keys=dk, tags={"door", "doorR", "front", "noedge"}, oplan=oR,
               bom=("문 겉판(오른)", "pine", doorh, dw_R, td, f"왼쪽 끝 앞쪽 반 턱 {r:g}×{hd:g}"), dev=rect(dw_R, doorh)))
        A(_box("오른문 겉판(턱)", xm + r + g, W - t - g, hd, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorR", "noedge"}))
        if gasket_on():
            A(_box("턱 가스켓", xm + g / 2, xm + r, hd - d["gk"], hd, dz0 + 20, dz1 - 20, "gasket", tags={"door", "gasket"},
                   keys={"rebate", "gasket", "gasket_w"}))
        for side, x0, x1 in (("왼", d["cx0"] + pg, xm - pg), ("오른", xm + pg, d["cx1"] - pg)):
            tg = {"door", "doorL" if side == "왼" else "doorR", "plug"}
            A(_box(f"{side}문 단열재", x0, x1, td, td + ti, pz0, pz1, "ins", keys={"t_ins", "plug_gap"}, tags=tg,
                   bom=("문 단열재", "ins", pz1 - pz0, x1 - x0, ti, "플러그")))
            A(_box(f"{side}문 속판", x0, x1, td + ti, td + s, pz0, pz1, "cedar", keys={"t_in", "plug_gap"}, tags=tg,
                   bom=("문 속판", "cedar", pz1 - pz0, x1 - x0, tl, "플러그")))

        # --- 자석 캐치(문틀 띠에 매립, 문 겉판 뒷면에 철판)
        mz = [zt1 - s / 2]
        if int(p["mag_n"]) >= 2:
            mz.append(dz0 + s / 2)
        for zc in mz:
            for sgn in (-1, 1):
                xc = xm + sgn * p["mag_off"]
                A(_box("자석 캐치", xc - md / 2, xc + md / 2, yf, yf + 6, zc - md / 2, zc + md / 2, "steel",
                       keys={"mag_n", "mag_d", "mag_off"}, tags={"mag"}, shape="disc"))

    # --- 선반(착탈, 통풍 슬롯) + 선반받이
    zs0, zs1 = d["zs0"], d["zs1"]
    sx0, sx1 = d["cx0"] + 2, d["cx1"] - 2
    sy0, sy1 = y0i + 2, d["cy1"] - 2
    sl = shelf_slots(sx1 - sx0, sy1 - sy0)
    A(_box("선반", sx0, sx1, sy0, sy1, zs0, zs1, "pine", keys={"lower_h", "shelf_t", "vent_w", "vent_pitch"}, tags={"shelf"},
           slots=[(sx0 + a, sy0 + b, w, h) for a, b, w, h in sl],
           bom=("선반(착탈)", "pine", sx1 - sx0, sy1 - sy0, p["shelf_t"], f"통풍 슬롯 {p['vent_w']:g}×{sy1 - sy0 - 80:.0f} {len(sl)}개"),
           dev=rect(sx1 - sx0, sy1 - sy0), dev_slots=sl))
    cl = p["cleat"]
    for nm, x0 in (("선반받이(좌)", d["cx0"]), ("선반받이(우)", d["cx1"] - cl)):
        A(_box(nm, x0, x0 + cl, y0i, d["cy1"], zs0 - cl, zs0, "pine", keys={"lower_h", "cleat"}, tags={"cleat"},
               bom=("선반받이", "pine", d["cy1"] - y0i, cl, cl, "옆속판에 나사")))

    # --- 열원
    if p["heat"] == "film":
        fm_, fwmax = p["film_margin"], p["film_w"]
        fl = []

        def film(nm, a, b):
            wa, wb = a - 2 * fm_, b - 2 * fm_
            if wa <= 0 or wb <= 0:
                return None
            c1, c2 = (min(wa, fwmax), wb), (min(wb, fwmax), wa)
            w1, l1 = max(c1, c2, key=lambda c: c[0] * c[1])
            return (nm, w1, l1)
        fc = faces()
        e = 1.0
        fkey = {"film_w", "film_margin", "film_faces", "heat"}
        if "뒤" in fc:
            fl.append(film("뒤", a1 - a0 - 2 * tl, zt1 - zb1 - 2 * s))
            A(_box("필름(뒤)", a0 + tl + fm_, a1 - tl - fm_, b1 - e, b1, zb1 + s + fm_, zt1 - s - fm_, "film", tags={"film"}, keys=fkey))
        if "위" in fc:
            fl.append(film("위", a1 - a0, b1 - y0i))
            A(_box("필름(위)", a0 + fm_, a1 - fm_, y0i + fm_, b1 - fm_, zt1 - ti - e, zt1 - ti, "film", tags={"film"}, keys=fkey))
        if "아래" in fc:
            fl.append(film("아래", a1 - a0, b1 - y0i))
            A(_box("필름(아래)", a0 + fm_, a1 - fm_, y0i + fm_, b1 - fm_, zb1 + ti, zb1 + ti + e, "film", tags={"film"}, keys=fkey))
        for nm, x in (("좌", a0), ("우", a1 - e)):
            if nm in fc:
                fl.append(film(nm, b1 - y0i, zt1 - zb1 - 2 * s))
                A(_box(f"필름({nm})", x, x + e, y0i + fm_, b1 - fm_, zb1 + s + fm_, zt1 - s - fm_, "film", tags={"film"}, keys=fkey))
        d["films"] = [x for x in fl if x]
        d["power"] = sum(w * l for _, w, l in d["films"]) / 1e6 * p["film_wpm2"]
    else:
        pw, pdp, ph = p["ptc_w"], p["ptc_d"], p["ptc_h"]
        yc = (y0i + d["cy1"]) / 2
        A(_box("PTC 히터", xm - pw / 2, xm + pw / 2, yc - pdp / 2, yc + pdp / 2, d["cz0"], d["cz0"] + ph, "ptc",
               tags={"ptc"}, keys={"ptc_w", "ptc_d", "ptc_h", "ptc_watt", "heat"}))
        d["films"] = []
        d["power"] = p["ptc_watt"]

    # --- 거치대: 뒷속판 → 문 안쪽 면 rack_front 앞까지
    rt, L, yb_in = d["rack_top"], d["rack_len"], d["cy1"]
    rk = {"rack", "rack_drop", "rack_gap", "rack_back", "rack_front", "rack_r", "n_bows", "bow_pitch"}
    if p["rack"] == "1":
        prof = rack1_profile(L)
        for sgn in (-1, 1):
            xc = xm + sgn * p["rack_gap"] / 2
            A(_box("삼각 받침", xc - p["r1_w"] / 2, xc + p["r1_w"] / 2, yb_in - L, yb_in, rt - p["r1_h"], rt + p["r1_lip"],
                   "ply", keys=rk | {"r1_w", "r1_h", "r1_tip", "r1_lip"}, tags={"rack"},
                   prof=[(yb_in - u, rt - p["r1_h"] + v) for u, v in prof], round_top=True,
                   bom=("삼각 받침", "ply", L, p["r1_h"] + p["r1_lip"], p["r1_w"], f"윗면 모서리 R{p['rack_r']:g}, 형판: 상세도"),
                   dev=[(u, v) for u, v in prof]))
        d["supports"] = [(-p["rack_gap"] / 2, rt), (p["rack_gap"] / 2, rt)]
    elif p["rack"] == "2":
        dd = p["r2_d"]
        emb = tl + ti + 12
        for sgn in (-1, 1):
            xc = xm + sgn * p["rack_gap"] / 2
            A(_box("둥근 막대", xc - dd / 2, xc + dd / 2, yb_in - L, yb_in + emb, rt - dd, rt, "ply",
                   keys=rk | {"r2_d"}, tags={"rack"}, shape="cyl",
                   bom=("둥근 막대", "ply", L + emb, dd, dd, f"Ø{dd:g}, 끝 R{min(p['rack_r'], dd / 2):g}, 뒷판 12 박음")))
        d["supports"] = [(-p["rack_gap"] / 2, rt), (p["rack_gap"] / 2, rt)]
    else:
        a, cw, chh = p["r3_arm"], p["r3_cap_w"], p["r3_cap_h"]
        A(_box("줌걸이 각재", xm - a / 2, xm + a / 2, yb_in - L, yb_in, rt - chh - a, rt - chh, "ply",
               keys=rk | {"r3_arm"}, tags={"rack"}, bom=("줌걸이 각재", "ply", L, a, a, "뒷판까지 볼트")))
        A(_box("줌 받침", xm - cw / 2, xm + cw / 2, yb_in - L, yb_in - p["rack_back"] + 5, rt - chh, rt, "ply",
               keys=rk | {"r3_cap_w", "r3_cap_h"}, tags={"rack"}, round_top=True,
               bom=("줌 받침", "ply", L - p["rack_back"] + 5, cw, chh, f"윗면 R{p['rack_r']:g}")))
        d["supports"] = [(0.0, rt)]

    if not is_bandaji():
        # --- 원목 손잡이(3D·평단면용)
        zc_h = (dz0 + dz1) / 2
        for sgn, tg in ((-1, "doorL"), (1, "doorR")):
            xc = xm + sgn * 40
            A(_box("원목 손잡이", xc - 6, xc + 6, -22, 0, zc_h - 50, zc_h + 50, "ply", tags={"door", tg, "handle"},
                   keys={"door_h"}))
        # --- 철물(정면 표시용)
        hw = []
        nh = max(int(p["hinges"]), 1)
        for k in range(nh):
            zc = dz0 + 60 + (doorh - 120) * (k / (nh - 1) if nh > 1 else 0.5)
            for x in (t, W - t):
                hw.append(("경첩", x, zc))
        d["hardware"] = hw
    return parts, d


def rack1_profile(L):
    """삼각 받침 옆모습(u: 뒷면에서 앞으로, v: 아래에서 위로)"""
    p = P()
    h, tip, lip = p["r1_h"], p["r1_tip"], p["r1_lip"]
    R = max(lip, 6.0)
    pts = [(0, 0), (0, h), (L - 2 * R, h)]
    for a in np.linspace(math.pi, 0, 13):          # 끝 턱(둥근 혹)
        pts.append((L - R + R * math.cos(a), h + lip * math.sin(a)))
    pts += [(L, h - tip)]
    return pts


# ---------------------------------------------------------------- 반닫이 문판 열림
def bj_point(d, u, v, th):
    """문판 위의 점(u: 경첩에서 문판을 따라 위로, v: 앞쪽으로)을 열림 각 th(도)만큼 돌린 위치 (y, z)"""
    t = math.radians(th)
    return (-u * math.sin(t) - v * math.cos(t), d["door_z"][0] + u * math.cos(t) - v * math.sin(t))


def bj_poly(d, th, length=None):
    """열린 문판 겉판 외곽(y, z)"""
    L = (d["door_z"][1] - d["door_z"][0]) if length is None else length
    td = P()["t_door"]
    return [bj_point(d, u, v, th) for u, v in ((0, 0), (L, 0), (L, -td), (0, -td))]


def bj_open(d):
    """반닫이 문판이 열리는 각도와 닿는 곳. 지지대가 있으면 90°"""
    p = P()
    if int(p["bj_stays"]) > 0:
        return 90.0, "지지대"
    L = d["door_z"][1] - d["door_z"][0]
    pts = [(L, 0.0), (L, -p["t_door"]), (L - 60, 22.0), (L - 80, 22.0)]   # 문판 끝 모서리, 손잡이
    th = 90.0
    while th < 180.0:
        th += 0.25
        for u, v in pts:
            y, z = bj_point(d, u, v, th)
            if z <= 0:
                return th - 0.25, "바닥"
            if y > 0 and z < d["door_z"][0]:
                return th - 0.25, "아래 앞판"
    return 180.0, "아래 앞판"


# ---------------------------------------------------------------- 부린활 형상
def bow_curves(d, state):
    """state: open(벌어짐) / closed(오므라짐). 반환: (외곽 x,z), (안쪽 x,z), 맨 위(외곽) z"""
    p = P()
    lb = p["bow_limb"]
    if state == "open":
        a, h = p["bow_open_span"] / 2, p["bow_open_h"]
        phi = np.linspace(-math.pi / 2, math.pi / 2, 181)
    else:
        a, h = p["bow_ring_w"] / 2, p["bow_ring_h"] / 2
        lim = math.pi - math.radians(25)
        phi = np.linspace(-lim, lim, 241)
    fx = lambda a_, ph: a_ * np.sin(ph)
    fz = lambda h_, ph: h_ * (1 - np.cos(ph))
    ai, hi = a - lb, h - lb / (1 if state == "open" else 2)
    ztop_in = -1e9
    for xs, zs in d["supports"]:
        ph = math.asin(min(abs(xs) / max(ai, 1), 1.0))
        ztop_in = max(ztop_in, zs + fz(hi, ph))
    zt = ztop_in + lb
    xo, zo = d["xm"] + fx(a, phi), zt - fz(h, phi)
    xi, zi = d["xm"] + fx(ai, phi), ztop_in - fz(hi, phi)
    return (xo, zo), (xi, zi), zt


def checks(parts, d):
    """여유 검사 결과: [(항목, 값, 기준, ok)]"""
    p = P()
    c = p["clear"]
    res = []
    for st, nm in (("open", "벌어진 활"), ("closed", "오므라든 활")):
        (xo, zo), _, zt = bow_curves(d, st)
        res.append((f"{nm} 좌우 여유", min(xo.min() - d["cx0"], d["cx1"] - xo.max()), c))
        res.append((f"{nm} 위 여유", d["cz1"] - zt, c))
        res.append((f"{nm} 아래 여유(선반 위)", zo.min() - d["zs1"], c))
    n = int(p["n_bows"])
    need = p["rack_back"] + n * p["bow_pitch"] + (p["r1_lip"] if p["rack"] == "1" else 10.0)
    res.append((f"거치대 남는 길이 (활 {n}장)", d["rack_len"] - need, 0.0))
    res.append(("문 열린 높이 − 벌어진 활 높이", d["open_h"] - p["bow_open_h"], 0.0))
    return [(a, b, cc, b >= cc - 1e-6) for a, b, cc in res]


# ---------------------------------------------------------------- 그리기 도구
A3 = (420.0, 297.0)
CREDIT = "@용현정 이동철"


def new_sheet(title, sub, no, total, scale_txt):
    fig = plt.figure(figsize=(A3[0] / 25.4, A3[1] / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, A3[0]); ax.set_ylim(0, A3[1]); ax.axis("off")
    ax.add_patch(Rectangle((10, 10), 400, 277, fill=False, lw=0.8))
    # 표제란
    x0, y0, w, h = 270, 10, 140, 26
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, lw=0.6))
    ax.plot([x0, x0 + w], [y0 + 13, y0 + 13], lw=0.4, color="k")
    ax.plot([x0 + 95, x0 + 95], [y0, y0 + 13], lw=0.4, color="k")
    ax.text(x0 + 4, y0 + 19.5, "각궁 점화장 제작도면", fontsize=11, va="center", weight="bold")
    ax.text(x0 + w - 4, y0 + 19.5, title, fontsize=9, va="center", ha="right")
    ax.text(x0 + 4, y0 + 6.5, sub, fontsize=6.5, va="center")
    ax.text(x0 + 97, y0 + 9, f"축척 {scale_txt}", fontsize=6.5, va="center")
    ax.text(x0 + 97, y0 + 3.5, f"{no} / {total}   {datetime.date.today():%Y-%m-%d}", fontsize=6, va="center")
    ax.text(x0 + w - 3, y0 + 9, CREDIT, fontsize=6.5, va="center", ha="right", weight="bold", color="#5a3d1e")
    return fig, ax


def view_axes(fig, x, y, xr, yr, scale):
    """종이 (x,y)mm 위치에 모델 범위 xr, yr 를 1:scale 로 배치"""
    w = (xr[1] - xr[0]) / scale
    h = (yr[1] - yr[0]) / scale
    ax = fig.add_axes([x / A3[0], y / A3[1], w / A3[0], h / A3[1]])
    ax.set_xlim(*xr); ax.set_ylim(*yr); ax.set_aspect("equal"); ax.axis("off")
    ax._scale = scale
    return ax


def dim(ax, p1, p2, off, text=None, fs=6, color="k"):
    """p1→p2 치수선, off: 종이 mm 수직 오프셋(+ 왼쪽 법선)"""
    s = getattr(ax, "_scale", 1)
    p1, p2 = np.array(p1, float), np.array(p2, float)
    v = p2 - p1
    L = np.linalg.norm(v)
    if L < 1e-6:
        return
    n = np.array([-v[1], v[0]]) / L
    o = n * off * s
    a, b = p1 + o, p2 + o
    ext = n * np.sign(off) * 1.5 * s
    for q, r in ((p1, a), (p2, b)):
        ax.plot([q[0] + n[0] * 0.8 * s * np.sign(off), r[0] + ext[0]], [q[1] + n[1] * 0.8 * s * np.sign(off), r[1] + ext[1]],
                lw=0.3, color=color, clip_on=False)
    ax.annotate("", a, b, arrowprops=dict(arrowstyle="<|-|>", lw=0.4, color=color, shrinkA=0, shrinkB=0,
                mutation_scale=5), annotation_clip=False)
    ang = math.degrees(math.atan2(v[1], v[0]))
    if ang > 90.1 or ang < -89.9:
        ang += 180
    m = (a + b) / 2 + n * 1.2 * s * (1 if off >= 0 else -1)
    ax.text(m[0], m[1], text if text is not None else f"{L:.0f}", rotation=ang, ha="center",
            va="bottom" if off >= 0 else "top", fontsize=fs, color=color, clip_on=False, rotation_mode="anchor")


def label(ax, xy, txt, dxdy, fs=5.5):
    s = ax._scale
    ax.annotate(txt, xy, (xy[0] + dxdy[0] * s, xy[1] + dxdy[1] * s), fontsize=fs,
                arrowprops=dict(arrowstyle="-", lw=0.3), annotation_clip=False, va="center")


def _poly(ax, pts, mat, lw=0.5, z=1, alpha=1.0, ls="-"):
    col = MAT[mat][1]
    ax.add_patch(Polygon(pts, closed=True, fc=col, ec="k" if mat not in ("film",) else col, lw=lw, zorder=z,
                         alpha=alpha, ls=ls))


def proj(part, view):
    x0, x1, y0, y1, z0, z1 = part["b"]
    if view == "front":
        return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    if view == "side":
        return [(y0, z0), (y1, z0), (y1, z1), (y0, z1)]
    return [(x0, -y0), (x1, -y0), (x1, -y1), (x0, -y1)]   # plan: y 아래로


def _round_rect(x0, z0, w, h, R):
    """윗모서리 둥근 사각형(단면)"""
    R = min(R, w / 2, h)
    pts = [(x0, z0), (x0 + w, z0), (x0 + w, z0 + h - R)]
    pts += [(x0 + w - R + R * math.cos(a), z0 + h - R + R * math.sin(a)) for a in np.linspace(0, math.pi / 2, 8)]
    pts += [(x0 + R + R * math.cos(a), z0 + h - R + R * math.sin(a)) for a in np.linspace(math.pi / 2, math.pi, 8)]
    return pts


def draw_holes(ax, q, ls="-", fc="#333"):
    for kind, xc, zc, w, h in q.get("holes", []):
        ax.add_patch(Rectangle((xc - w / 2, zc - h / 2), w, h, fc=fc, ec="k", lw=0.4, zorder=6, ls=ls))
        if kind == "recp":
            p = P()
            for sgn in (-1, 1):
                ax.add_patch(Circle((xc + sgn * p["recp_pitch"] / 2, zc), p["recp_hole"] / 2, fc=fc, ec="k", lw=0.3, zorder=6, ls=ls))


def draw_front(ax, parts, d, opened):
    """정면도. opened=True면 문을 떼어낸 내부 모습(아래 앞판은 비침)"""
    p = P()
    if opened:
        sel = [q for q in parts if "door" not in q["tags"] and "lowfront" not in q["tags"]]
    else:   # 문 닫힘: 겉에서 보이는 겉판·문·발만
        sel = [q for q in parts if q["mat"] == "pine" and q["tags"] & {"shell", "door", "foot"} and "back" not in q["tags"]]
    for q in sorted(sel, key=lambda q: -q["b"][2]):
        x0, x1, _, _, z0, z1 = q["b"]
        if q.get("shape") == "cyl":
            ax.add_patch(Circle(((x0 + x1) / 2, (z0 + z1) / 2), (x1 - x0) / 2, fc=MAT[q["mat"]][1], ec="k", lw=0.5, zorder=3))
            continue
        if q.get("shape") == "disc":
            ax.add_patch(Circle(((x0 + x1) / 2, (z0 + z1) / 2), (x1 - x0) / 2, fc=MAT["steel"][1], ec="k", lw=0.3, zorder=5))
            continue
        if q["mat"] == "film":
            if x1 - x0 < 3:
                ax.plot([x0, x0], [z0, z1], color=MAT["film"][1], lw=1.2, zorder=4)
            elif z1 - z0 < 3:
                ax.plot([x0, x1], [z0, z0], color=MAT["film"][1], lw=1.2, zorder=4)
            else:
                ax.add_patch(Polygon(proj(q, "front"), fc="none", ec=MAT["film"][1], lw=0.8, ls="--", zorder=2.5))
            continue
        if q.get("round_top"):
            ax.add_patch(Polygon(_round_rect(x0, z0, x1 - x0, z1 - z0, p["rack_r"]), fc=MAT[q["mat"]][1], ec="k", lw=0.5, zorder=3))
            continue
        if opened and "front" in q["tags"]:          # 아래 앞판: 비치게
            ax.add_patch(Polygon(proj(q, "front"), fc=MAT[q["mat"]][1], ec="k", lw=0.5, zorder=5, alpha=0.35))
            draw_holes(ax, q, fc="none")
            continue
        if "shelf" in q["tags"]:
            ax.add_patch(Polygon(proj(q, "front"), fc=MAT[q["mat"]][1], ec="k", lw=0.5, zorder=3))
            continue
        _poly(ax, proj(q, "front"), q["mat"], lw=0.5, z=2)
        if not opened:
            draw_holes(ax, q)
    if opened:
        for q in parts:
            if "back" in q["tags"]:
                draw_holes(ax, q, ls="--", fc="none")
    else:
        for q in parts:
            if "back" in q["tags"]:
                draw_holes(ax, q, ls=":", fc="none")
        xm = d["xm"]
        dz0, dz1 = d["door_z"]
        if is_bandaji():
            for _, xc, zc in d["hardware"]:     # 맞경첩: 문판 아래 끝, 축만 보임
                ax.add_patch(Rectangle((xc - 32, zc - 4), 64, 6, fc="#8a7a5a", ec="k", lw=0.3, zorder=5))
            ax.add_patch(Rectangle((xm - 60, dz1 - 80), 120, 20, fc="#6b4b2a", ec="k", lw=0.3, zorder=5))
        else:
            for _, x, zc in d["hardware"]:      # 맞경첩: 문 옆면에 묻히고 축만 보임
                xg = x + (p["gap"] / 2 if x < d["xm"] else -p["gap"] / 2)
                ax.add_patch(Rectangle((xg - 3, zc - 32), 6, 64, fc="#8a7a5a", ec="k", lw=0.3, zorder=5))
            zc = (dz0 + dz1) / 2
            for sgn in (-1, 1):
                ax.add_patch(Rectangle((xm + sgn * 40 - 6, zc - 50), 12, 100, fc="#6b4b2a", ec="k", lw=0.3, zorder=5))


def draw_bows(ax, d, view, n_all=True):
    p = P()
    for st, col, ls in (("open", "#1f5fbf", "--"), ("closed", "#2e8b57", "-.")):
        (xo, zo), (xi, zi), zt = bow_curves(d, st)
        if view == "front":
            ax.plot(xo, zo, color=col, lw=0.8, ls=ls, zorder=7)
            ax.plot(xi, zi, color=col, lw=0.5, ls=ls, zorder=7)
        else:
            n = int(p["n_bows"])
            for k in range(n):
                yc = d["cy1"] - p["rack_back"] - p["bow_pitch"] * (k + 0.5)
                w = p["bow_pitch"] * 0.8
                ax.add_patch(Rectangle((yc - w / 2, zo.min()), w, zt - zo.min(), fill=False, ec=col, lw=0.6, ls=ls, zorder=7))


def draw_side(ax, parts, d, xc):
    for q in sorted(parts, key=lambda q: q["mat"] == "film"):
        x0, x1 = q["b"][0], q["b"][1]
        if not (x0 <= xc <= x1):
            continue
        if "prof" in q:
            _poly(ax, q["prof"], q["mat"], z=3)
            continue
        if q.get("shape") == "cyl":
            _, _, y0, y1, z0, z1 = q["b"]
            ax.add_patch(Rectangle((y0, z0), y1 - y0, z1 - z0, fc=MAT[q["mat"]][1], ec="k", lw=0.5, zorder=3))
            continue
        if q["mat"] == "film":
            _, _, y0, y1, z0, z1 = q["b"]
            if y1 - y0 < 3:
                ax.plot([y0, y0], [z0, z1], color=MAT["film"][1], lw=1.2, zorder=4)
            else:
                ax.plot([y0, y1], [z0, z0], color=MAT["film"][1], lw=1.2, zorder=4)
            continue
        if "noedge" in q["tags"]:
            ax.add_patch(Polygon(proj(q, "side"), fc=MAT[q["mat"]][1], ec=MAT[q["mat"]][1], lw=0.3, zorder=2))
            if "oplan" in q:
                yy = max(v[1] for v in q["oplan"])
                z0, z1 = q["b"][4], q["b"][5]
                ax.add_patch(Rectangle((0, z0), yy, z1 - z0, fill=False, ec="k", lw=0.5, zorder=3))
            continue
        _poly(ax, proj(q, "side"), q["mat"], z=2 if q["mat"] != "gasket" else 4)


def draw_plan(ax, parts, d, zc):
    for q in parts:
        z0, z1 = q["b"][4], q["b"][5]
        if not (z0 <= zc <= z1):
            continue
        if q["mat"] == "film":
            x0, x1, y0, y1, _, _ = q["b"]
            if x1 - x0 < 3:
                ax.plot([x0, x0], [-y0, -y1], color=MAT["film"][1], lw=1.2, zorder=4)
            else:
                ax.plot([x0, x1], [-y0, -y0], color=MAT["film"][1], lw=1.2, zorder=4)
            continue
        if "noedge" in q["tags"]:
            ax.add_patch(Polygon(proj(q, "plan"), fc=MAT[q["mat"]][1], ec=MAT[q["mat"]][1], lw=0.3, zorder=2))
            if "oplan" in q:
                ax.add_patch(Polygon([(x, -y) for x, y in q["oplan"]], fill=False, ec="k", lw=0.5, zorder=3))
            continue
        _poly(ax, proj(q, "plan"), q["mat"], z=2 if q["mat"] != "gasket" else 4)


def legend(ax, x, y):
    for i, k in enumerate(("pine", "ins", "cedar", "ply", "gasket")):
        ax.add_patch(Rectangle((x + i * 26, y), 5, 3.5, fc=MAT[k][1], ec="k", lw=0.3))
        ax.text(x + i * 26 + 6.5, y + 1.75, MAT[k][0], fontsize=5.5, va="center")
    xx = x + 5 * 26
    ax.plot([xx, xx + 5], [y + 1.75] * 2, color=MAT["film"][1], lw=1.2)
    ax.text(xx + 6.5, y + 1.75, "면상필름", fontsize=5.5, va="center")
    ax.plot([xx + 26, xx + 31], [y + 1.75] * 2, color="#1f5fbf", lw=0.8, ls="--")
    ax.text(xx + 32.5, y + 1.75, "벌어진 부린활", fontsize=5.5, va="center")
    ax.plot([xx + 58, xx + 63], [y + 1.75] * 2, color="#2e8b57", lw=0.8, ls="-.")
    ax.text(xx + 64.5, y + 1.75, "오므라든 부린활", fontsize=5.5, va="center")


def pick_scale(w, h, aw, ah):
    for s in (5, 10, 20, 25, 50):
        if w / s <= aw and h / s <= ah:
            return s
    return 40


def rack_xcut(d):
    p = P()
    return d["xm"] + (p["rack_gap"] / 2 if p["rack"] in ("1", "2") else 0.0)


# ---------------------------------------------------------------- 시트
def sheet_assembly(pdf, parts, d):
    p = P()
    W, H, D = p["W"], p["H"], p["D"]
    m = 60
    ext = p["door_h"] + 20 if is_bandaji() else 0.0
    s = pick_scale(2 * (W + 2 * m) + (D + 2 * m + ext), H + D + 4 * m, 380, 235)
    kind = "반닫이" if is_bandaji() else "양문 여닫이"
    fig, ax0 = new_sheet("조립도", f"{kind} · 부린활 {int(p['n_bows'])}장 · W{W:g}×H{H:g}×D{D:g}", 1, 5, f"1:{s}")
    gx = 22
    top = 268
    # 정면도(문 닫힘)
    y_front = top - (H + m) / s - 8
    a1 = view_axes(fig, gx, y_front, (-m, W + m), (-m * 0.6, H + m * 0.4), s)
    draw_front(a1, parts, d, False)
    dim(a1, (0, H), (W, H), 6, f"{W:g}")
    dim(a1, (0, 0), (0, H), 6, f"{H:g}")
    dz0, dz1 = d["door_z"]
    dim(a1, (W, 0), (W, dz0), -6, f"{dz0:.0f}")
    dim(a1, (W, dz0), (W, dz1), -6, f"문 {dz1 - dz0:.0f}")
    tx, tz, tw, th = d["thermo"]
    bw, bh = p["bezel_w"], p["bezel_h"]
    a1.add_patch(Rectangle((tx - bw / 2, tz - bh / 2), bw, bh, fill=False, ec="k", lw=0.5, ls="--", zorder=7))
    dim(a1, (tx - bw / 2, tz - bh / 2), (tx + bw / 2, tz - bh / 2), -3, f"타공 {tw:g}×{th:g} (테두리 {bw:g}×{bh:g})", fs=5)
    ax0.text(gx + m / s, y_front + (H + m * 0.6) / s + 11, "정면도 (문 닫힘)", fontsize=8, weight="bold")
    # 정면도(문 열림)
    gx2 = gx + (W + 2 * m) / s + 6
    a2 = view_axes(fig, gx2, y_front, (-m, W + m), (-m * 0.6, H + m * 0.4), s)
    draw_front(a2, parts, d, True)
    draw_bows(a2, d, "front")
    dim(a2, (d["cx0"], d["cz1"]), (d["cx1"], d["cz1"]), 4, f"안 {d['cw']:.0f}")
    dim(a2, (d["cx0"], d["zs1"]), (d["cx0"], d["cz1"]), 4, f"활 칸 {d['ch']:.0f}")
    dim(a2, (d["cx0"], d["cz0"]), (d["cx0"], d["zs0"]), 4, f"하부 {p['lower_h']:g}", fs=5)
    dim(a2, (d["cx1"], d["rack_top"]), (d["cx1"], d["cz1"]), -4, f"{p['rack_drop']:g}")
    if p["rack"] in ("1", "2"):
        dim(a2, (d["xm"] - p["rack_gap"] / 2, d["rack_top"]), (d["xm"] + p["rack_gap"] / 2, d["rack_top"]), 3, f"{p['rack_gap']:g}", fs=5)
    ax0.text(gx2 + m / s, y_front + (H + m * 0.6) / s + 11, "정면도 (문 떼어냄 · 내부)", fontsize=8, weight="bold")
    # 측단면도
    xc = rack_xcut(d)
    gx3 = gx2 + (W + 2 * m) / s + 6
    a3 = view_axes(fig, gx3, y_front, (-m - ext, D + m), (-m * 0.6, H + m * 0.4), s)
    draw_side(a3, parts, d, xc)
    draw_bows(a3, d, "side")
    if is_bandaji():     # 열린 문판(점선)과 경첩 축, 문판 끝이 지나는 궤적
        dz0, dz1 = d["door_z"]
        hh = dz1 - dz0
        ang, where = d["bj_angle"], d["bj_contact"]
        a3.add_patch(Polygon(bj_poly(d, ang), fill=False, ec="#b5651d", lw=0.7, ls="--", zorder=8))
        if int(p["bj_stays"]) == 0 and ang > 90.5:
            a3.add_patch(Polygon(bj_poly(d, 90.0), fill=False, ec="#b5651d", lw=0.4, ls=":", zorder=8))
        a3.add_patch(Circle((0, dz0), 6, fill=False, ec="#b5651d", lw=0.7, zorder=8))
        th_ = np.linspace(0, math.radians(ang), 40)
        a3.plot(-hh * np.sin(th_), dz0 + hh * np.cos(th_), color="#b5651d", lw=0.4, ls=":")
        a3.plot([-max(hh, 40) - 20, 0], [0, 0], color="k", lw=0.5)
        ty, tz = bj_point(d, hh * 0.55, 0, ang)
        a3.text(ty, tz + 55, f"열린 문판 {ang:.0f}° ({where}에 닿음)" if where != "지지대" else "열린 문판 90° (지지대)",
                fontsize=5, ha="center", color="#b5651d")
    dim(a3, (0, H), (D, H), 6, f"{D:g}")
    dim(a3, (d["cy1"] - d["rack_len"], d["rack_top"] + 30), (d["cy1"], d["rack_top"] + 30), 2, f"{d['rack_len']:.0f}", fs=5)
    dim(a3, (d["cy0"], d["zs1"]), (d["cy1"], d["zs1"]), -2, f"안 {d['cd']:.0f}", fs=5)
    ax0.text(gx3 + (m + ext) / s, y_front + (H + m * 0.6) / s + 11, "측단면도 A-A", fontsize=8, weight="bold")
    # 평단면도
    zc = d["rack_top"] - (p["r1_h"] / 2 if p["rack"] == "1" else 10)
    yp = y_front - (D + 2 * m) / s - 4
    a4 = view_axes(fig, gx, yp, (-m, W + m), (-D - m, m), s)
    draw_plan(a4, parts, d, zc)
    dim(a4, (0, -D), (W, -D), -5, f"{W:g}")
    dim(a4, (W, 0), (W, -D), 5, f"{D:g}")
    ax0.text(gx + m / s, yp + (D + 2 * m) / s - 2, "평단면도 B-B (거치대 높이)", fontsize=8, weight="bold")
    # 단면 위치 표시
    a1.plot([xc, xc], [-m * 0.4, H + m * 0.2], lw=0.4, ls=(0, (8, 3, 1, 3)), color="k")
    a1.text(xc, H + m * 0.25, "A", fontsize=6, ha="center")
    a1.plot([-m * 0.5, W + m * 0.5], [zc, zc], lw=0.4, ls=(0, (8, 3, 1, 3)), color="k")
    a1.text(-m * 0.55, zc, "B", fontsize=6, ha="right", va="center")
    # 배면도(뒤에서 봄: 좌우 반대)
    a5 = view_axes(fig, gx2, yp - (H - D) / s, (-m, W + m), (-m * 0.6, H + m * 0.4), s)
    a5.add_patch(Rectangle((0, p["foot_h"]), W, H - p["foot_h"], fc=MAT["pine"][1], ec="k", lw=0.6))
    a5.add_patch(Rectangle((p["t"], d["zb1"]), W - 2 * p["t"], d["zt1"] - d["zb1"], fill=False, ec="k", lw=0.4))
    for x_ in (10, W - 10 - p["foot_w"]):
        a5.add_patch(Rectangle((x_, 0), p["foot_w"], p["foot_h"], fc=MAT["pine"][1], ec="k", lw=0.5))
    rx, rz, rw, rh = d["recp"]
    rxb = W - rx
    a5.add_patch(Rectangle((rxb - rw / 2, rz - rh / 2), rw, rh, fc="#333", ec="k", lw=0.4))
    for sg in (-1, 1):
        a5.add_patch(Circle((rxb + sg * p["recp_pitch"] / 2, rz), max(p["recp_hole"], 6) / 2, fc="#333", ec="k", lw=0.3))
    near = W if rxb > W / 2 else 0
    dim(a5, (min(near, rxb), rz + 60), (max(near, rxb), rz + 60), 1, f"{abs(near - rxb):.0f}", fs=5)
    dim(a5, (rxb + 40, 0), (rxb + 40, rz), -1 if rxb > W / 2 else 1, f"{rz:.0f}", fs=5)
    ax0.text(gx2 + m / s, yp - (H - D) / s + (H + m * 0.6) / s + 3, "배면도 (전원 리셉터클)", fontsize=8, weight="bold")
    # 검사 결과
    res = checks(parts, d)
    x, y = gx3 - 2, yp + (D + 2 * m) / s - 4
    ax0.text(x, y, "여유 검사", fontsize=7.5, weight="bold")
    for i, (nm, v, c, ok) in enumerate(res):
        ax0.text(x, y - 4.2 * (i + 1), f"{'○' if ok else '×'} {nm}: {v:.0f} mm (기준 ≥ {c:g})", fontsize=6,
                 color="k" if ok else "#c00000")
    legend(ax0, 22, 40)
    ax0.text(22, 48, f"열원: {'면상필름 ' + ', '.join(faces()) if p['heat'] == 'film' else 'PTC 히터(하부 바닥)'}  ·  "
             f"약 {d['power']:.0f} W  ·  설정 {p['set_temp']:g} ℃", fontsize=6.5)
    pdf.savefig(fig); plt.close(fig)


def sheet_parts(pdf, parts, d):
    p = P()
    items = []
    seen = set()
    for q in parts:
        b = q.get("bom")
        if not b or q.get("dev") is None:
            continue
        key = (b[0], round(b[2]), round(b[3]))
        if key in seen:
            continue
        seen.add(key)
        qty = sum(1 for r in parts if r.get("bom") and (r["bom"][0], round(r["bom"][2]), round(r["bom"][3])) == key)
        items.append((b, q["dev"], qty, q))
    # 큰 판 → 축척 10 기준 배치
    big = [it for it in items if it[0][1] == "pine"]
    big.sort(key=lambda it: -np.array(it[1])[:, 1].max())
    s = pick_scale(max(max(np.array(it[1])[:, 0].max() for it in big), 1), 1, 120, 1e9)
    s = max(s, 10)
    fig, ax0 = new_sheet("부재도", "겉판·문·선반 전개 (사개 손·타공·통풍 슬롯 포함)", 2, 5, f"1:{s}")
    x, y, rowh = 20, 278, 0
    for b, dev, qty, q in big:
        pts = np.array(dev, float)
        w, h = pts[:, 0].max() - pts[:, 0].min(), pts[:, 1].max() - pts[:, 1].min()
        # 길이 방향을 가로로
        pw, ph = w / s, h / s
        if x + pw + 25 > 405:
            x, y = 20, y - rowh - 16
            rowh = 0
        a = view_axes(fig, x, y - ph - 6, (pts[:, 0].min() - 10, pts[:, 0].max() + 10), (pts[:, 1].min() - 10, pts[:, 1].max() + 10), s)
        a.add_patch(Polygon(pts, fc=MAT["pine"][1], ec="k", lw=0.6))
        for kind, hx, hz, hw_, hh_ in q.get("dev_holes", []):
            a.add_patch(Rectangle((hx - hw_ / 2, hz - hh_ / 2), hw_, hh_, fc="w", ec="k", lw=0.4))
            if kind == "recp":
                for sg in (-1, 1):
                    a.add_patch(Circle((hx + sg * p["recp_pitch"] / 2, hz), max(p["recp_hole"], 5) / 2, fc="w", ec="k", lw=0.3))
            dim(a, (0, hz), (hx - hw_ / 2, hz), 2, f"{hx - hw_ / 2:.0f}", fs=4.5)
            dim(a, (hx + hw_ / 2 + 4, 0), (hx + hw_ / 2 + 4, hz - hh_ / 2), -1.5, f"{hz - hh_ / 2:.0f}", fs=4.5)
        if q.get("dev_cleat"):
            for xx in (q["dev_cleat"], w - q["dev_cleat"]):
                a.plot([xx, xx], [0, h], color="k", lw=0.5)
        for sx_, sy_, sw_, sh_ in q.get("dev_slots", []):
            a.add_patch(Rectangle((sx_, sy_), sw_, sh_, fc="w", ec="k", lw=0.3))
        dim(a, (0, h), (w, h), 3, f"{w:.0f}", fs=5.5)
        dim(a, (0, 0), (0, h), 3, f"{h:.0f}", fs=5.5)
        ax0.text(x, y + 0.5, f"{b[0]}  ×{qty}  (t{b[4]:g})", fontsize=6.5, weight="bold")
        if b[5]:
            ax0.text(x, y - ph - 9, b[5], fontsize=5.5, color="#444")
        x += pw + 30
        rowh = max(rowh, ph + 10)
    # 사개 설명
    bn = pins(p["D"], p["pin_pitch"])
    ax0.text(20, 52, f"사개: 깊이 {p['D']:g} 을 {len(bn) - 1}구간(손 간격 {bn[1]:.1f})으로 나눔. 천판·지판은 짝수 구간(앞뒤 끝 포함)이 손, "
             f"옆판은 홀수 구간이 손. 손 길이 = 겉판 두께 {p['t']:g}.", fontsize=6)
    ax0.text(20, 46, f"뒷판·아래 앞판은 옆판·천판·지판 안쪽에 홈({p['dado']:g}) 파서 끼움 — 재단표 치수에 홈 깊이 포함. 타공 위치는 앞(안쪽)에서 본 치수.", fontsize=6)
    ax0.text(20, 40, (f"반닫이 문판: 가운데 판(가로결) 양끝에 마구리 {p['bj_cleat']:g}(세로결)를 촉(10)으로 끼움 — 풀칠은 가운데만.  " if is_bandaji() else
             "문 겉판: 왼문 오른쪽 끝 뒤쪽 반, 오른문 왼쪽 끝 앞쪽 반을 턱으로 깎아 겹침(턱맞춤) — 상세도 참조.  ")
             + f"선반: 선반받이({p['cleat']:g}각) 위에 얹기만 함(착탈), 통풍 슬롯 폭 {p['vent_w']:g} 간격 {p['vent_pitch']:g}.", fontsize=6)
    pdf.savefig(fig); plt.close(fig)


def sheet_rack(pdf, parts, d, no, total):
    p = P()
    L = d["rack_len"]
    kind = p["rack"]
    if kind == "1":
        hh = p["r1_h"] + p["r1_lip"]
    elif kind == "2":
        hh = p["r2_d"]
        L = L + p["t_in"] + p["t_ins"] + 12
    else:
        hh = p["r3_arm"] + p["r3_cap_h"]
    s = 1 if (L + 60 <= 360 and hh + 60 <= 200) else 2
    name = {"1": "① 삼각 받침 ×2", "2": "② 둥근 막대 ×2", "3": "③ 줌걸이 ×1"}[kind]
    fig, ax0 = new_sheet("거치대 상세", f"거치대 {name} · 부린활 {int(p['n_bows'])}장", no, total,
                         f"1:{s}" + (" (형판)" if s == 1 else ""))
    x0, y0 = 30, 120
    if kind == "1":
        prof = np.array(rack1_profile(d["rack_len"]))
        a = view_axes(fig, x0, y0, (-20, L + 40), (-30, hh + 40), s)
        a.add_patch(Polygon(prof, fc=MAT["ply"][1], ec="k", lw=0.8))
        dim(a, (0, hh), (L, hh), 8, f"{L:.0f}")
        dim(a, (0, 0), (0, p["r1_h"]), 6, f"{p['r1_h']:g}")
        dim(a, (L, p["r1_h"] - p["r1_tip"]), (L, p["r1_h"]), -6, f"{p['r1_tip']:g}")
        R = max(p["r1_lip"], 6)
        dim(a, (L - 2 * R, p["r1_h"]), (L, p["r1_h"]), -3, f"{2 * R:g}", fs=5)
        dim(a, (L + 8, p["r1_h"]), (L + 8, hh), -3, f"턱 {p['r1_lip']:g}", fs=5)
        for k in range(int(p["n_bows"])):
            u0 = p["rack_back"] + p["bow_pitch"] * k
            a.add_patch(Rectangle((u0, p["r1_h"]), p["bow_pitch"], 6, fill=False, ec="#1f5fbf", lw=0.4))
            a.text(u0 + p["bow_pitch"] / 2, p["r1_h"] + 9, f"활{k + 1}", fontsize=5, ha="center", color="#1f5fbf")
        a.text(-14, p["r1_h"] + 20, "뒷속판 쪽", rotation=90, fontsize=6, ha="center", va="center")
        a.text(L * 0.35, p["r1_h"] * 0.55, f"두께(폭) {p['r1_w']:g} 집성목\n뒷면 나사 2개로 뒷판까지 고정\n결 방향: 길이 방향", fontsize=6.5, ha="center")
    elif kind == "2":
        a = view_axes(fig, x0, y0, (-20, L + 40), (-40, hh + 40), s)
        a.add_patch(Rectangle((0, 0), L, hh, fc=MAT["ply"][1], ec="k", lw=0.8))
        Lw = d["rack_len"]
        for x_, w_, m_ in ((Lw, p["t_in"], "cedar"), (Lw + p["t_in"], p["t_ins"], "ins"), (Lw + p["t_in"] + p["t_ins"], p["t"], "pine")):
            a.add_patch(Rectangle((x_, -15), w_, hh + 30, fc=MAT[m_][1], ec="k", lw=0.4, ls="--", alpha=0.6))
        dim(a, (0, hh), (L, hh), 8, f"{L:.0f}")
        dim(a, (0, 0), (0, hh), 6, f"Ø{hh:g}")
        for k in range(int(p["n_bows"])):
            u0 = Lw - p["rack_back"] - p["bow_pitch"] * (k + 1)
            a.add_patch(Rectangle((u0, hh), p["bow_pitch"], 5, fill=False, ec="#1f5fbf", lw=0.4))
        a.text(L / 2, -25, f"끝 R3 다듬기 · 속판·단열재 관통 후 뒷판에 12 박아 접착 · 내민 길이 {Lw:.0f}", fontsize=6.5, ha="center")
    else:
        aa, cw, chh = p["r3_arm"], p["r3_cap_w"], p["r3_cap_h"]
        a = view_axes(fig, x0, y0, (-20, L + 40), (-aa - 40, chh + 40), s)
        a.add_patch(Rectangle((0, -aa), L, aa, fc=MAT["ply"][1], ec="k", lw=0.8))
        a.add_patch(Rectangle((0, 0), L - p["rack_back"] + 5, chh, fc=MAT["ply"][1], ec="k", lw=0.8))
        dim(a, (0, chh), (L, chh), 8, f"{L:.0f}")
        dim(a, (0, -aa), (0, 0), 6, f"{aa:g}")
        dim(a, (0, 0), (0, chh), 12, f"{chh:g}")
        a.text(L / 2, -aa - 20, f"받침 폭 {cw:g}, 윗면 줌통이 앉도록 둥글게. 각재는 뒷판까지 볼트 2개", fontsize=6.5, ha="center")
    ax0.text(x0, y0 + (hh + 80) / s + 14, f"거치대 {name} 옆모습", fontsize=9, weight="bold")
    # 단면(활 닿는 부분 라운드)
    R = p["rack_r"]
    if kind in ("1", "3"):
        cw_ = p["r1_w"] if kind == "1" else p["r3_cap_w"]
        ch_ = 50.0 if kind == "1" else p["r3_cap_h"]
        sx, sy = 330, 40
        b = view_axes(fig, sx, sy, (-20, cw_ + 30), (-20, ch_ + 30), 1)
        b.add_patch(Polygon(_round_rect(0, 0, cw_, ch_, R), fc=MAT["ply"][1], ec="k", lw=0.7))
        if kind == "1":
            b.plot([0, cw_], [0, 0], color="w", lw=2)
            b.text(cw_ / 2, 8, "(아래 생략)", fontsize=5, ha="center")
        dim(b, (0, ch_), (cw_, ch_), 6, f"{cw_:g}", fs=5.5)
        b.text(cw_ + 4, ch_ - R / 2, f"R{R:g}", fontsize=6)
        ax0.text(sx, sy + (ch_ + 50) + 2, "단면 — 활 닿는 윗면 라운드 (1:1)", fontsize=7.5, weight="bold")
    ax0.text(x0, 107, f"• 거치대 앞끝은 문 안쪽 면(단열 플러그)에서 {p['rack_front']:g} 띄움 → 길이 = 안쪽 깊이 {d['cd']:.0f} − {p['rack_front']:g} = {d['rack_len']:.0f}", fontsize=7)
    ax0.text(x0, 100, f"• 활 {int(p['n_bows'])}장 × {p['bow_pitch']:g} (궁대 포함) + 뒤 여유 {p['rack_back']:g} 가 들어감, 활 닿는 모서리는 모두 R{R:g}", fontsize=7)
    if kind in ("1", "2"):
        ax0.text(x0, 93, f"• 두 개를 가운데에서 좌우 {p['rack_gap'] / 2:g}씩(중심 간격 {p['rack_gap']:g}) 설치, 윗면 = 속 천장에서 {p['rack_drop']:g} 아래", fontsize=7)
    else:
        ax0.text(x0, 93, f"• 가운데 1개, 받침 윗면 = 속 천장에서 {p['rack_drop']:g} 아래", fontsize=7)
    ax0.text(x0, 86, "• 부린활은 줌통 쪽이 위로 가게 걸고, 벌어진 활도 그대로 걸 수 있음", fontsize=7)
    if s == 1:
        ax0.text(x0, 79, "• 배율 100%로 출력하면 그대로 형판으로 쓸 수 있음 (아래 50 mm 눈금으로 확인)", fontsize=7)
        ax0.plot([x0, x0 + 50], [70, 70], color="k", lw=0.8)
        for k in range(6):
            ax0.plot([x0 + k * 10] * 2, [70, 72], color="k", lw=0.5)
        ax0.text(x0 + 52, 70, "50 mm", fontsize=6, va="center")
    pdf.savefig(fig); plt.close(fig)


def sheet_seal(pdf, parts, d, no, total):
    p = P()
    fig, ax0 = new_sheet("밀폐·단열 상세", "문받이 · " + ("반닫이 경첩부" if is_bandaji() else "양문 턱맞춤") + " · 가스켓 · 벽 구성", no, total, "1:1")
    zc = (d["door_z"][0] + d["door_z"][1]) / 2
    t, td = p["t"], p["t_door"]
    span = td + d["s"] + 45
    sd = 1
    b1 = view_axes(fig, 30, 165, (-10, span), (-span, 10), sd)
    draw_plan(b1, parts, d, zc)
    ax0.text(30, 165 + (span + 10) / sd + 6, "상세 1 · 옆판 앞 모서리 평단면", fontsize=8, weight="bold")
    label(b1, (t / 2, -span + 15), "옆판", (-8, -6))
    label(b1, (t + 40, -td / 2), "문 겉판", (6, 8))
    label(b1, (t + p["t_ins"] / 2, -td - 30), "단열재", (10, -4))
    label(b1, (t + p["t_ins"] + p["t_in"] / 2, -td - 38), "속판", (8, -8))
    if gasket_on():
        label(b1, (t + d["s"] / 2, -td - 1), "가스켓", (16, 2))
    label(b1, (t + d["s"] / 2, -d["yfront"] - p["frame_d"] / 2), "문틀 띠", (16, -2))
    label(b1, (t + d["s"] + 25, -td - 5), "문 플러그", (10, -14))
    xm = d["xm"]
    if is_bandaji():
        dz0 = d["door_z"][0]
        b2 = view_axes(fig, 140, 165, (-50, span - 20), (dz0 - 50, dz0 + span - 40), sd)
        draw_side(b2, parts, d, xm - 100)
        b2.add_patch(Polygon(bj_poly(d, d["bj_angle"], 70), fill=False, ec="#b5651d", lw=0.8, ls="--", zorder=8))
        b2.add_patch(Circle((0, dz0), 3, fill=False, ec="#b5651d", lw=0.8, zorder=8))
        label(b2, (0, dz0), "경첩 축(앞면 선)", (-8, -10))
        label(b2, bj_point(d, 40, 0, d["bj_angle"]), f"{d['bj_angle']:.0f}° 열린 문판", (-4, 10))
        ax0.text(140, 165 + (span + 10) / sd + 6, "상세 2 · 반닫이 경첩부 측단면", fontsize=8, weight="bold")
    else:
        b2 = view_axes(fig, 140, 165, (xm - 55, xm + 55), (-span, 10), sd)
        draw_plan(b2, parts, d, zc)
        dim(b2, (xm + p["gap"] / 2, -td), (xm + p["rebate"], -td), -4, f"턱 {p['rebate']:g}", fs=5.5)
        dim(b2, (xm - 50, 0), (xm - 50, -td / 2), 4, f"{td / 2:g}", fs=5.5)
        if gasket_on():
            label(b2, (xm + p["rebate"] / 2, -td / 2), "가스켓", (14, 6))
        label(b2, (xm - 30, -td / 4), "왼문", (-6, 8))
        label(b2, (xm + 30, -td / 4), "오른문", (4, 8))
        ax0.text(140, 165 + (span + 10) / sd + 6, "상세 2 · 양문 맞닿는 곳 평단면", fontsize=8, weight="bold")
    b3 = view_axes(fig, 30, 45, (-10, span), (p["H"] - span, p["H"] + 10), sd)
    draw_side(b3, parts, d, xm - 100)
    label(b3, (span - 20, p["H"] - t / 2), "천판", (6, 4))
    label(b3, (td / 2, p["H"] - t - 30), "문 겉판", (12, -6))
    ax0.text(30, 45 + (span + 20) / sd + 4, "상세 3 · 위 문받이 측단면", fontsize=8, weight="bold")
    zr = d["door_z"][0]
    b4 = view_axes(fig, 140, 45, (-10, span), (zr - 50, zr + span - 40), sd)
    draw_side(b4, parts, d, xm - 100)
    label(b4, (p["t"] / 2, zr - 40), "아래 앞판", (14, -4))
    label(b4, (d["yfront"] + p["frame_d"] / 2, zr), "문틀 띠", (16, 4))
    ax0.text(140, 45 + (span + 20) / sd + 4, "상세 4 · 문 아래 문받이 측단면", fontsize=8, weight="bold")
    x = 275
    ax0.text(x, 270, "밀폐·단열 구조", fontsize=9, weight="bold")
    gtxt = (f"D형 가스켓 {p['gasket_w']:g}×{p['gasket_h']:g} (눌림 {d['gk']:g})" if gasket_on() else "가스켓 없음(맞닿음)")
    notes = [
        f"• 벽(뒤·위·아래·좌·우): 겉판 {t:g} + 단열재 {p['t_ins']:g} + 면상필름 + 삼나무 속판 {p['t_in']:g}",
        f"• 문틀 띠: 단열층 앞 둘레에 원목 띠(깊이 {p['frame_d']:g}) — 문이 닿는 면",
        f"• 문: 겉판 {td:g} 뒤에 단열 플러그(단열재 + 속판), 둘레 {p['plug_gap']:g} 작게",
        f"• 문받이: {gtxt}",
        (f"• 반닫이 문판: 한 장, 양끝 마구리 {p['bj_cleat']:g}(촉 끼움, 휨 방지)" if is_bandaji()
         else f"• 양문: 턱맞춤 {p['rebate']:g} (두께 반씩 깎아 겹침)" + (" + 턱에 가스켓" if gasket_on() else "")),
        ((f"• 경첩 {int(p['bj_hinges'])}개를 문판 아래 끝 앞면 선에 축이 오게, 지지대 {int(p['bj_stays'])}개로 90°에서 멈춤" if int(p['bj_stays']) > 0
          else f"• 경첩 {int(p['bj_hinges'])}개(180° 열리는 맞경첩)를 문판 아래 끝 앞면 선에 축이 오게, 문판은 {d['bj_angle']:.0f}°에서 {d['bj_contact']}에 닿음") if is_bandaji()
         else f"• 경첩은 문 한 짝당 {int(p['hinges'])}개 (맞경첩, 옆면 매립)"),
        f"• 자석 캐치 Ø{p['mag_d']:g}: 문틀 띠(위{'·아래' if int(p['mag_n']) >= 2 else ''})에 매립,",
        f"   가운데에서 좌우 {p['mag_off']:g}, 문 겉판 뒷면에 철판 — 저절로 열리지 않음",
        f"• 문 둘레 틈 {p['gap']:g}",
        "• 전선·센서 구멍은 지름 8 이하, 내열 실리콘으로 메움",
        "• 단열재: 압출 폴리스티렌 또는 열반사 단열재",
    ]
    for i, s_ in enumerate(notes):
        ax0.text(x, 260 - i * 6, s_, fontsize=6.3)
    legend(ax0, 30, 25)
    pdf.savefig(fig); plt.close(fig)


def bom_rows(parts):
    rows = {}
    for q in parts:
        b = q.get("bom")
        if not b:
            continue
        nm, mat, L, Wd, T, note = b
        L, Wd = max(L, Wd), min(L, Wd)
        k = (nm, mat, round(L, 1), round(Wd, 1), round(T, 1), note)
        rows[k] = rows.get(k, 0) + 1
    order = {"pine": 0, "ins": 1, "cedar": 2, "ply": 3}
    return [(k[0], MAT[k[1]][0], qty, k[2], k[3], k[4], k[5]) for k, qty in
            sorted(rows.items(), key=lambda kv: (order.get(kv[0][1], 9), -kv[0][2]))]


def hardware_rows(d):
    p = P()
    nh = max(int(p["hinges"]), 1)
    nm_ = max(int(p["mag_n"]), 1)
    side = "왼쪽" if p["ctl_side"] != "R" else "오른쪽"
    if is_bandaji():
        r = [("맞경첩(황동)", int(p["bj_hinges"]), "문판 아래 끝, 축이 앞면 선에 오게 파서 묻음"),
             (("문판 지지대(스테이)", int(p["bj_stays"]), "양옆, 문판을 90°에서 받침") if int(p["bj_stays"]) > 0 else
              ("문판 끝 펠트·고무 받침", 2, f"문판이 {d['bj_angle']:.0f}°에서 {d['bj_contact']}에 닿는 곳 보호")),
             ("자석 캐치(매립)·철판", 2 * nm_, f"Ø{p['mag_d']:g}, 위 문틀 띠"),
             ("원목 손잡이(가로)", 1, "문판 위 가운데, 뒤에서 나사")]
    else:
        r = [("맞경첩(황동)", nh * 2, f"문 한 짝당 {nh}, 문·옆판 옆면에 파서 묻음(겉에 철물 없음)"),
             ("자석 캐치(매립)·철판", nm_ * 2, f"Ø{p['mag_d']:g}, 문 한 짝당 {nm_}"),
             ("원목 손잡이", 2, "문 가운데 쪽, 뒤에서 나사")]
    if gasket_on():
        r.append(("D형 가스켓", 1, f"{p['gasket_w']:g}×{p['gasket_h']:g}, 약 {gasket_len(d) / 1000:.1f} m"))
    r.append(("온습도 조절기(XM-18형)", 1, f"아래 앞판 {side}, 테두리 {p['bezel_w']:g}×{p['bezel_h']:g}, 타공 {p['thermo_w']:g}×{p['thermo_h']:g}, 깊이 {p['ctl_depth']:g}"))
    r.append(("온도·습도 센서", 2, "활 옆 중간 높이, 선 구멍 Ø8 실리콘 마감"))
    r.append(("전원 리셉터클(IEC 인렛)", 1, f"뒷판 아래 {side}, 수평, 타공 {p['recp_w']:g}×{p['recp_h']:g}, 나사 {p['recp_pitch']:g}"))
    if p["heat"] == "film":
        for nm, w, l in d["films"]:
            r.append((f"면상필름({nm})", 1, f"{w:.0f}×{l:.0f}"))
    else:
        r.append(("PTC 히터", 1, f"{p['ptc_watt']:g} W, {p['ptc_w']:g}×{p['ptc_d']:g}×{p['ptc_h']:g}, 하부 바닥 가운데"))
    r.append(("휴즈·배선", 1, f"합계 약 {d['power']:.0f} W"))
    return r


def gasket_len(d):
    p = P()
    W, t, s = p["W"], p["t"], d["s"]
    dz0, dz1 = d["door_z"]
    meet = 0 if is_bandaji() else (dz1 - dz0)
    return (W - 2 * t) + (W - 2 * t - 2 * s) + 2 * (dz1 - dz0) + meet


def sheet_bom(pdf, parts, d):
    p = P()
    fig, ax0 = new_sheet("재단표 · 철물 · 전기", "치수 mm (길이 × 폭 × 두께)", 5, 5, "—")
    rows = bom_rows(parts)
    ax0.text(20, 278, "재단표", fontsize=9, weight="bold")
    hdr = ("부재", "재료", "수량", "길이", "폭", "두께", "비고")
    xs = (20, 68, 92, 108, 128, 148, 165)
    y = 270
    for x, h in zip(xs, hdr):
        ax0.text(x, y, h, fontsize=6.5, weight="bold")
    ax0.plot([20, 255], [y - 2, y - 2], lw=0.4, color="k")
    for r in rows:
        y -= 5.2
        vals = (r[0], r[1], f"{r[2]}", f"{r[3]:.0f}", f"{r[4]:.0f}", f"{r[5]:g}", r[6])
        for x, v in zip(xs, vals):
            ax0.text(x, y, v, fontsize=6)
    y -= 10
    ax0.text(20, y, "철물 · 전기", fontsize=9, weight="bold")
    y -= 7
    for nm, q, note in hardware_rows(d):
        ax0.text(20, y, nm, fontsize=6); ax0.text(68, y, f"{q}", fontsize=6); ax0.text(80, y, note, fontsize=6)
        y -= 5.2
    # 오른쪽: 주요 치수, 검사, 주기
    x = 270
    ax0.text(x, 278, "주요 치수", fontsize=9, weight="bold")
    info = [
        f"외형 W{p['W']:g} × H{p['H']:g} × D{p['D']:g}",
        f"안쪽(활 칸) {d['cw']:.0f} × {d['ch']:.0f} × {d['cd']:.0f}",
        f"문 형식 {'반닫이(문판 앞으로 젖힘)' if is_bandaji() else '양문 여닫이'}",
        f"문 높이 {d['door_z'][1] - d['door_z'][0]:.0f} (천판 아래부터), 문 열린 높이 {d['open_h']:.0f}",
        f"하부 공간 안높이 {p['lower_h']:g}, 선반 윗면 {d['zs1']:.0f} / 문 하단 {d['door_z'][0]:.0f}",
        f"부린활 {int(p['n_bows'])}장 × {p['bow_pitch']:g} (궁대 포함)",
        f"벌어진 활 {p['bow_open_span']:g} × {p['bow_open_h']:g}",
        f"오므라든 활 {p['bow_ring_w']:g} × {p['bow_ring_h']:g}",
        f"거치대 {['', '① 삼각 받침', '② 둥근 막대', '③ 줌걸이'][int(p['rack'])]}, 길이 {d['rack_len']:.0f}",
    ]
    for i, s in enumerate(info):
        ax0.text(x, 270 - i * 5.2, s, fontsize=6.3)
    y = 270 - len(info) * 5.2 - 8
    ax0.text(x, y, "여유 검사", fontsize=9, weight="bold")
    for nm, v, c, ok in checks(parts, d):
        y -= 5.2
        ax0.text(x, y, f"{'○' if ok else '×'} {nm}: {v:.0f} (≥{c:g})", fontsize=6, color="k" if ok else "#c00000")
    y -= 10
    ax0.text(x, y, "주기", fontsize=9, weight="bold")
    notes = [
        "1. 겉판: 레드파인 집성목, 속판: 삼나무(향·습도 조절).",
        "2. 필름은 단열재와 속판 사이에 붙이고 속판은",
        "   필름에 못이 닿지 않게 가장자리만 고정.",
        "3. 온도조절기 센서는 활 옆 중간 높이, 속판에서 20 띄움.",
        f"4. 설정 {p['set_temp']:g} ℃ 기준, 과열 방지 휴즈 필수.",
        "5. 부린활은 벌어진 채로 넣어도 들어가도록 폭을 정함.",
        "6. 선반은 얹기만 하는 착탈식, 통풍 슬롯으로 아래위 공기 순환.",
        "7. PTC 히터는 금속 받침 위에, 속판에서 10 이상 띄움.",
        "8. 리셉터클 덮개가 옆으로 젖혀지므로 옆 여유 확보.",
    ]
    for s in notes:
        y -= 5.2
        ax0.text(x, y, s, fontsize=5.8)
    pdf.savefig(fig); plt.close(fig)


# ---------------------------------------------------------------- 출력
def to_dxf(path, parts, d):
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    for nm, col in (("CUT", 7), ("TEXT", 3), ("RACK", 1)):
        doc.layers.add(nm, color=col)
    x, y, rowh = 0.0, 0.0, 0.0
    seen = set()
    for q in parts:
        b, dev = q.get("bom"), q.get("dev")
        if not b or dev is None:
            continue
        key = (b[0], round(b[2]), round(b[3]))
        if key in seen:
            continue
        seen.add(key)
        pts = np.array(dev, float)
        w, h = pts[:, 0].max(), pts[:, 1].max()
        if x + w > 3000:
            x, y, rowh = 0.0, y - rowh - 80, 0.0
        lay = "RACK" if q["mat"] == "ply" else "CUT"
        msp.add_lwpolyline([(px + x, py + y - h) for px, py in pts], close=True, dxfattribs={"layer": lay})
        if q.get("dev_cleat"):
            for xx in (q["dev_cleat"], w - q["dev_cleat"]):
                msp.add_line((x + xx, y - h), (x + xx, y), dxfattribs={"layer": "CUT"})
        for sx_, sy_, sw_, sh_ in q.get("dev_slots", []):
            msp.add_lwpolyline([(x + sx_, y - h + sy_), (x + sx_ + sw_, y - h + sy_), (x + sx_ + sw_, y - h + sy_ + sh_), (x + sx_, y - h + sy_ + sh_)],
                               close=True, dxfattribs={"layer": "CUT"})
        for kind, hx, hz, hw_, hh_ in q.get("dev_holes", []):
            msp.add_lwpolyline([(x + hx - hw_ / 2, y - h + hz - hh_ / 2), (x + hx + hw_ / 2, y - h + hz - hh_ / 2),
                                (x + hx + hw_ / 2, y - h + hz + hh_ / 2), (x + hx - hw_ / 2, y - h + hz + hh_ / 2)],
                               close=True, dxfattribs={"layer": "CUT"})
            if kind == "recp":
                for sg in (-1, 1):
                    msp.add_circle((x + hx + sg * P()["recp_pitch"] / 2, y - h + hz), P()["recp_hole"] / 2, dxfattribs={"layer": "CUT"})
        msp.add_text(f"{b[0]} t{b[4]:g}", height=12, dxfattribs={"layer": "TEXT"}).set_placement((x, y + 10))
        x += w + 60
        rowh = max(rowh, h)
    doc.saveas(path)


def write_csv(path, parts, d):
    with open(path, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp)
        w.writerow(["부재", "재료", "수량", "길이", "폭", "두께", "비고"])
        for r in bom_rows(parts):
            w.writerow([r[0], r[1], r[2], f"{r[3]:.0f}", f"{r[4]:.0f}", f"{r[5]:g}", r[6]])
        w.writerow([])
        w.writerow(["철물·전기", "수량", "비고"])
        for r in hardware_rows(d):
            w.writerow(list(r))


def apply(params):
    if params:
        for k, v in params.items():
            if k in INT_KEYS:
                PARAM[k] = int(float(v))
            elif k in STR_KEYS:
                PARAM[k] = str(v)
            else:
                PARAM[k] = float(v)


def validate():
    """치명적 오류 목록"""
    p, d = P(), derive()
    e = []
    if d["cw"] <= 100 or d["ch"] <= 100 or d["cd"] <= 50:
        e.append("안쪽 공간이 너무 작습니다. 외형 치수나 두께를 확인하세요.")
    if int(p["n_bows"]) < 1:
        e.append("활 장수는 1 이상이어야 합니다.")
    if d["zs1"] > d["door_z"][0] + 1e-6:
        e.append(f"하부 공간 높이가 너무 높습니다: 선반 윗면 {d['zs1']:.0f} > 문짝 하단 {d['door_z'][0]:.0f}. "
                 f"하부 공간 안높이를 {p['lower_h'] - (d['zs1'] - d['door_z'][0]):.0f} 이하로 하거나 문 높이를 줄이세요.")
    if d["rail0"] <= d["zb1"] + d["s"] + 10:
        e.append("문 높이가 너무 큽니다. 문 아래에 아래 앞판이 남아야 합니다.")
    n = int(p["n_bows"])
    need = p["rack_back"] + n * p["bow_pitch"] + (p["r1_lip"] if p["rack"] == "1" else 10.0)
    if need > d["rack_len"]:
        e.append(f"활 {n}장이 거치대에 들어가지 않습니다: 필요 {need:.0f} > 거치대 {d['rack_len']:.0f}. 활 장수를 줄이거나 깊이를 늘리세요.")
    tx, tz, tw, th = d["thermo"]
    bw, bh = max(p["bezel_w"], tw), max(p["bezel_h"], th)
    if th > p["lower_h"]:
        e.append(f"조절기 몸체 세로({th:g})가 하부 공간 안높이({p['lower_h']:g})보다 큽니다.")
    if tz + bh / 2 > d["door_z"][0] - p["gap"] - 3:
        e.append("조절기 앞 테두리가 아래 앞판 위로 벗어납니다.")
    if p["thermo_x"] < p["t"] + 3 or p["thermo_x"] + bw > p["W"] - p["t"] - 3:
        e.append("조절기 앞 테두리가 옆판과 겹칩니다. 위치(옆판→테두리)를 확인하세요.")
    if (tx - tw / 2) < p["t"] + d["s"] or (tx + tw / 2) > p["W"] - p["t"] - d["s"]:
        e.append("조절기 몸체가 문틀 띠와 겹칩니다. 위치(옆판→테두리)를 늘리세요.")
    if p["ctl_depth"] > d["cy1"] - p["t"] - 20:
        e.append("조절기 깊이가 하부 공간 깊이보다 깁니다.")
    rx, rz, rw, rh = d["recp"]
    if rh > p["lower_h"]:
        e.append("리셉터클 타공이 하부 공간보다 큽니다.")
    if p["recp_x"] < p["t"] + d["s"] + 5:
        e.append("리셉터클이 옆판·단열층과 겹칩니다. 옆판→타공 거리를 늘리세요.")
    if p["heat"] == "film" and not faces():
        e.append("필름을 붙일 면을 하나 이상 선택하세요.")
    if p["heat"] == "ptc":
        if p["ptc_h"] > p["lower_h"] - p["cleat"]:
            e.append("PTC 히터가 하부 공간(선반받이 아래)보다 높습니다.")
        if p["ptc_d"] > d["cy1"] - d["y0i"] - 10 or p["ptc_w"] > d["cw"] - 2 * p["cleat"] - 10:
            e.append("PTC 히터가 하부 공간보다 큽니다.")
        # 조절기 몸체와 겹침
        yc = (d["y0i"] + d["cy1"]) / 2
        if (abs(tx - d["xm"]) < (tw + p["ptc_w"]) / 2 + 10) and (p["ctl_depth"] - 10 > yc - p["ptc_d"] / 2 - 10):
            e.append("PTC 히터가 온습도 조절기 몸체와 겹칩니다. 조절기 위치나 히터 크기를 확인하세요.")
    if p["rack"] not in ("1", "2", "3"):
        e.append("거치대 형식은 1, 2, 3 중 하나입니다.")
    if is_bandaji() and p["bj_cleat"] * 2 > d["cw"] / 2:
        e.append("반닫이 마구리 폭이 너무 큽니다.")
    if p.get("door_type") not in ("double", "bandaji"):
        e.append("문 형식은 double(양문) 또는 bandaji(반닫이)입니다.")
    if p["rebate"] >= d["cw"] / 4:
        e.append("턱 너비가 너무 큽니다.")
    return e


def generate(outdir="output", params=None):
    apply(params)
    errs = validate()
    if errs:
        raise ValueError("\n".join(errs))
    os.makedirs(outdir, exist_ok=True)
    parts, d = build()
    p = P()
    base = os.path.join(outdir, f"jeomhwajang_W{p['W']:.0f}_H{p['H']:.0f}_D{p['D']:.0f}_bow{int(p['n_bows'])}")
    files = [base + ".pdf", base + "_parts.dxf", base + "_cutlist.csv"]
    with PdfPages(files[0]) as pdf:
        sheet_assembly(pdf, parts, d)
        sheet_parts(pdf, parts, d)
        sheet_rack(pdf, parts, d, 3, 5)
        sheet_seal(pdf, parts, d, 4, 5)
        sheet_bom(pdf, parts, d)
    to_dxf(files[1], parts, d)
    write_csv(files[2], parts, d)
    return files


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for f_ in generate("output"):
        print(f_)
    pp, dd = build()
    for nm_, v_, c_, ok_ in checks(pp, dd):
        print(f"{'OK' if ok_ else 'NG'} {nm_}: {v_:.0f} (>= {c_:g})")
