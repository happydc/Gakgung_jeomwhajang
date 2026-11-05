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
    return None


_setup_font()
plt.rcParams["axes.unicode_minus"] = False

# ---------------------------------------------------------------- 기본값
PARAM = dict(
    # 본체
    W=920.0, H=950.0, D=320.0,      # 외형 가로·높이·깊이
    t=18.0,                         # 겉판 두께(옆판·천판·지판·뒷판·중간판)
    foot_h=30.0, foot_w=60.0,       # 발 높이·크기(4개)
    pin_pitch=40.0,                 # 사개 손 간격(목표)
    dado=6.0,                       # 중간판·뒷판 홈 깊이
    # 단열·밀폐
    t_ins=10.0,                     # 단열재 두께
    t_in=9.0,                       # 속판(삼나무) 두께
    gasket_w=9.0, gasket_h=6.0,     # 가스켓 폭·높이(D형)
    gap=2.0,                        # 문 둘레 틈
    plug_gap=3.0,                   # 문 단열 플러그 둘레 틈
    rebate=12.0,                    # 양문 맞닿는 턱 너비
    # 문·조절부
    t_door=18.0,                    # 문 겉판 두께
    hinges=2,                       # 문 한 짝당 경첩 수
    ctl_h=130.0,                    # 아래 조절부 칸 안높이(0이면 조절부 없음)
    thermo_w=71.0, thermo_h=29.0,   # 온도조절기 타공
    dial_w=46.0, dial_h=46.0,       # 다이얼(조광·타이머) 타공
    set_temp=30.0,                  # 설정 온도 ℃
    # 열원
    heat="film",                    # film | bulb
    film_faces="뒤,아래,좌,우",       # 필름 붙일 면: 뒤 위 아래 좌 우
    film_w=800.0,                   # 필름 최대 폭
    film_margin=20.0,               # 속판 가장자리 여유
    film_wpm2=200.0,                # 필름 소비전력 W/m²
    bulb_watt=150.0, bulb_d=125.0, bulb_h=180.0,   # 적외선 전구(소켓 포함 높이)
    # 거치대
    rack="1",                       # 1 삼각 받침 2개 / 2 둥근 막대 2개 / 3 줌걸이 1개
    rack_drop=100.0,                # 속 천장 → 거치대 윗면
    rack_gap=260.0,                 # 받침·막대 중심 간격(1·2형)
    rack_back=10.0,                 # 뒷속판 → 첫 활 사이 여유
    r1_w=40.0, r1_h=90.0, r1_tip=30.0, r1_lip=12.0,   # 삼각 받침: 폭, 높이, 끝 두께, 턱 높이
    r2_d=25.0,                      # 둥근 막대 지름
    r3_arm=40.0, r3_cap_w=120.0, r3_cap_h=30.0,       # 줌걸이: 각재 단면, 받침 폭·높이
    # 활
    n_bows=4,                       # 활 장수
    bow_pitch=50.0,                 # 활 1장(궁대 포함) 두께
    bow_open_span=800.0,            # 벌어진 부린활: 고자~고자 최대 폭
    bow_open_h=450.0,               # 벌어진 부린활: 줌통~고자 높이
    bow_ring_w=560.0, bow_ring_h=500.0,   # 오므라든 부린활 외경
    bow_limb=25.0,                  # 활채 너비(정면에서 보이는 두께)
    clear=20.0,                     # 활 둘레 최소 여유
)

FACE_NAMES = ("뒤", "위", "아래", "좌", "우")
INT_KEYS = ("hinges", "n_bows")
STR_KEYS = ("heat", "film_faces", "rack")

MAT = {
    "pine": ("레드파인", "#e8cc98"),
    "cedar": ("삼나무", "#f5e6c8"),
    "ins": ("단열재", "#f2b8c6"),
    "ply": ("집성목", "#c9a46a"),
    "steel": ("철물", "#555555"),
    "film": ("면상필름", "#e03030"),
    "gasket": ("가스켓", "#222222"),
    "bulb": ("전구", "#f08a3c"),
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
    """양 끝(길이 방향 0, length)에 사개 홈을 낸 판의 전개 외곽.
    bnds: 너비 방향 구간 경계, notch_odd=True면 홀수 구간을 깊이 t만큼 파냄"""
    segs = list(zip(bnds[:-1], bnds[1:]))
    cut = [(i % 2 == 1) == notch_odd for i in range(len(segs))]
    pts = []
    for (a, b), c in zip(segs, cut):                 # 왼쪽 끝, 아래→위
        x = t if c else 0.0
        pts += [(x, a), (x, b)]
    for (a, b), c in reversed(list(zip(segs, cut))):  # 오른쪽 끝, 위→아래
        x = length - t if c else length
        pts += [(x, b), (x, a)]
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) > 1e-9 or abs(out[-1][1] - p[1]) > 1e-9):
            out.append(p)
    return out


def rect(w, h):
    return [(0, 0), (w, 0), (w, h), (0, h)]


def derive():
    """주요 기준 치수"""
    p = P()
    t, ti, tl = p["t"], p["t_ins"], p["t_in"]
    W, H, D = p["W"], p["H"], p["D"]
    f = p["foot_h"]
    s = ti + tl                                  # 단열층 두께
    zb = f                                       # 지판 아랫면
    ctl = max(p["ctl_h"], 0.0)
    if ctl > 0:
        zd = f + t + ctl                         # 중간판 아랫면
    else:
        zd = f                                   # 조절부 없음: 지판이 곧 바닥
    zf = zd + t                                  # 중간판 윗면(겉)
    d = dict(
        s=s, zb=zb, zd=zd, zf=zf, ctl=ctl,
        cx0=t + s, cx1=W - t - s,
        cy0=p["t_door"] + s, cy1=D - t - s,
        cz0=zf + s, cz1=H - t - s,
        xm=W / 2,
    )
    d["cw"], d["cd"], d["ch"] = d["cx1"] - d["cx0"], d["cy1"] - d["cy0"], d["cz1"] - d["cz0"]
    d["rack_top"] = d["cz1"] - p["rack_drop"]
    n = int(p["n_bows"])
    d["rack_len"] = p["rack_back"] + n * p["bow_pitch"] + (p["r1_lip"] if p["rack"] == "1" else 15.0)
    return d


def faces():
    return [f.strip() for f in str(P()["film_faces"]).replace(" ", ",").split(",") if f.strip() in FACE_NAMES]


def build():
    """모든 부재 목록"""
    p, d = P(), derive()
    W, H, D = p["W"], p["H"], p["D"]
    t, ti, tl = p["t"], p["t_ins"], p["t_in"]
    f, td = p["foot_h"], p["t_door"]
    zd, zf = d["zd"], d["zf"]
    xm, g = d["xm"], p["gap"]
    parts = []
    A = parts.append

    # --- 몸체 겉판(사개: 천판·지판 ↔ 옆판, 깊이 방향)
    bn = pins(D, p["pin_pitch"])
    side_len = H - f
    A(_box("천판", 0, W, 0, D, H - t, H, "pine", keys={"W", "D", "t", "pin_pitch"},
           tags={"shell"}, bom=("천판", "pine", W, D, t, "사개"), dev=notched_board(W, D, bn, t, True)))
    A(_box("지판", 0, W, 0, D, f, f + t, "pine", keys={"W", "D", "t", "pin_pitch"},
           tags={"shell"}, bom=("지판", "pine", W, D, t, "사개"), dev=notched_board(W, D, bn, t, True)))
    for nm, x0 in (("옆판(좌)", 0), ("옆판(우)", W - t)):
        A(_box(nm, x0, x0 + t, 0, D, f, H, "pine", keys={"H", "D", "t", "pin_pitch", "foot_h"},
               tags={"shell"}, bom=("옆판", "pine", side_len, D, t, "사개, 들쇠"),
               dev=notched_board(side_len, D, bn, t, False)))
    A(_box("뒷판", t, W - t, D - t, D, f + t, H - t, "pine", keys={"W", "H", "t"}, tags={"shell"},
           bom=("뒷판", "pine", W - 2 * t + 2 * p["dado"], H - f - 2 * t + 2 * p["dado"], t, "홈 끼움")))
    if d["ctl"] > 0:
        yd = td + p["gasket_h"] * 0.5
        A(_box("중간판", t, W - t, yd, D - t, zd, zf, "pine", keys={"ctl_h", "t"}, tags={"shell"},
               bom=("중간판(조절부 위)", "pine", W - 2 * t + 2 * p["dado"], D - t - yd + p["dado"], t, "홈 끼움")))
        holes = []
        cxh = t + 40 + p["thermo_w"] / 2
        holes.append(("thermo", cxh, p["thermo_w"], p["thermo_h"]))
        holes.append(("dial", cxh + p["thermo_w"] / 2 + 40 + p["dial_w"] / 2, p["dial_w"], p["dial_h"]))
        A(_box("조절부 앞판", t, W - t, 0, t, f + t, zd + 0.0, "pine", keys={"ctl_h", "thermo_w", "thermo_h", "dial_w", "dial_h"},
               tags={"shell", "front"}, holes=holes,
               bom=("조절부 앞판", "pine", W - 2 * t, zd - f - t, t, "온도조절기·다이얼 타공")))
    # 발
    fw = p["foot_w"]
    for i, (x0, y0) in enumerate(((10, 10), (W - 10 - fw, 10), (10, D - 10 - fw), (W - 10 - fw, D - 10 - fw))):
        A(_box("발", x0, x0 + fw, y0, y0 + fw, 0, f, "pine", keys={"foot_h", "foot_w"},
              tags={"foot"}, bom=("발", "pine", fw, fw, f, "") if f > 0 else None))

    # --- 단열층 + 속판 (위·아래가 전체, 옆이 그 사이, 뒤가 가장 안쪽)
    xi0, xi1 = t, W - t
    zt1 = H - t                       # 천판 아랫면
    gk = p["gasket_h"] * 0.5          # 가스켓 눌린 두께
    yfront = td + gk                  # 문받이 면(단열층 앞 가장자리)
    yb = D - t                        # 뒷판 앞면
    # 단열재
    A(_box("단열재(위)", xi0, xi1, yfront, yb, zt1 - ti, zt1, "ins", keys={"t_ins"}, tags={"ins"},
           bom=("단열재 위", "ins", xi1 - xi0, yb - yfront, ti, "")))
    A(_box("단열재(아래)", xi0, xi1, yfront, yb, zf, zf + ti, "ins", keys={"t_ins"}, tags={"ins"},
           bom=("단열재 아래", "ins", xi1 - xi0, yb - yfront, ti, "")))
    for nm, x0 in (("단열재(좌)", xi0), ("단열재(우)", xi1 - ti)):
        A(_box(nm, x0, x0 + ti, yfront, yb, zf + ti, zt1 - ti, "ins", keys={"t_ins"}, tags={"ins"},
               bom=("단열재 옆", "ins", zt1 - zf - 2 * ti, yb - yfront, ti, "")))
    A(_box("단열재(뒤)", xi0 + ti, xi1 - ti, yb - ti, yb, zf + ti, zt1 - ti, "ins", keys={"t_ins"}, tags={"ins"},
           bom=("단열재 뒤", "ins", xi1 - xi0 - 2 * ti, zt1 - zf - 2 * ti, ti, "")))
    # 속판
    a0, a1 = xi0 + ti, xi1 - ti
    b1 = yb - ti
    A(_box("속판(위)", a0, a1, yfront, b1, zt1 - ti - tl, zt1 - ti, "cedar", keys={"t_in"}, tags={"lining"},
           bom=("속판 위", "cedar", a1 - a0, b1 - yfront, tl, "")))
    A(_box("속판(아래)", a0, a1, yfront, b1, zf + ti, zf + ti + tl, "cedar", keys={"t_in"}, tags={"lining"},
           bom=("속판 아래", "cedar", a1 - a0, b1 - yfront, tl, "")))
    for nm, x0 in (("속판(좌)", a0), ("속판(우)", a1 - tl)):
        A(_box(nm, x0, x0 + tl, yfront, b1, zf + ti + tl, zt1 - ti - tl, "cedar", keys={"t_in"}, tags={"lining"},
               bom=("속판 옆", "cedar", zt1 - zf - 2 * (ti + tl), b1 - yfront, tl, "")))
    A(_box("속판(뒤)", a0 + tl, a1 - tl, b1 - tl, b1, zf + ti + tl, zt1 - ti - tl, "cedar", keys={"t_in"}, tags={"lining"},
           bom=("속판 뒤", "cedar", a1 - a0 - 2 * tl, zt1 - zf - 2 * (ti + tl), tl, "")))

    # --- 문받이 가스켓(단열층 앞 가장자리 둘레, 문 겉판 뒷면에 닿음)
    gw, gh = p["gasket_w"], p["gasket_h"]
    gc = (ti + tl) / 2
    gy0, gy1 = td, yfront
    A(_box("가스켓(위)", xi0, xi1, gy0, gy1, zt1 - gc - gw / 2, zt1 - gc + gw / 2, "gasket", tags={"gasket"},
           keys={"gasket_w", "gasket_h"}))
    A(_box("가스켓(아래)", xi0, xi1, gy0, gy1, zf + gc - gw / 2, zf + gc + gw / 2, "gasket", tags={"gasket"},
           keys={"gasket_w", "gasket_h"}))
    for x in (xi0 + gc, xi1 - gc):
        A(_box("가스켓(옆)", x - gw / 2, x + gw / 2, gy0, gy1, zf, zt1, "gasket", tags={"gasket"},
               keys={"gasket_w", "gasket_h"}))

    # --- 문(양문): 겉판 + 턱맞춤, 뒤에 단열 플러그(단열재 + 속판)
    r = p["rebate"]
    dz0, dz1 = zd + g if d["ctl"] > 0 else zf + g, H - t - g
    if d["ctl"] == 0:
        dz0 = f + t + g
    hd = td / 2
    dk = {"t_door", "gap", "rebate"}
    # 왼문: 앞쪽 반은 xm-g/2까지, 뒤쪽 반은 xm+r까지(턱)
    oL = [(t + g, 0), (xm - g / 2, 0), (xm - g / 2, hd), (xm + r, hd), (xm + r, td), (t + g, td)]
    oR = [(xm + g / 2, 0), (W - t - g, 0), (W - t - g, td), (xm + r + g, td), (xm + r + g, hd), (xm + g / 2, hd)]
    A(_box("왼문 겉판", t + g, xm - g / 2, 0, hd, dz0, dz1, "pine", keys=dk, tags={"door", "doorL", "front", "noedge"}, oplan=oL))
    A(_box("왼문 겉판(턱)", t + g, xm + r, hd, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorL", "noedge"}))
    A(_box("오른문 겉판", xm + g / 2, W - t - g, 0, hd, dz0, dz1, "pine", keys=dk, tags={"door", "doorR", "front", "noedge"}, oplan=oR))
    A(_box("오른문 겉판(턱)", xm + r + g, W - t - g, hd, td, dz0, dz1, "pine", keys=dk, tags={"door", "doorR", "noedge"}))
    A(_box("턱 가스켓", xm + g / 2, xm + r, hd - gh * 0.3, hd, dz0 + 20, dz1 - 20, "gasket", tags={"door", "gasket"},
           keys={"rebate", "gasket_w"}))
    dw_L = xm + r - (t + g)
    dw_R = (W - t - g) - (xm + g / 2)
    doorh = dz1 - dz0
    parts[-5]["bom"] = ("문 겉판(왼)", "pine", doorh, dw_L, td, f"오른쪽 끝 뒤쪽 반 턱 {r:g}×{hd:g}")
    parts[-3]["bom"] = ("문 겉판(오른)", "pine", doorh, dw_R, td, f"왼쪽 끝 앞쪽 반 턱 {r:g}×{hd:g}")
    parts[-5]["dev"] = rect(dw_L, doorh)
    parts[-3]["dev"] = rect(dw_R, doorh)
    pg = p["plug_gap"]
    pz0, pz1 = d["cz0"] + pg, d["cz1"] - pg
    for side, x0, x1 in (("왼", d["cx0"] + pg, xm - pg), ("오른", xm + pg, d["cx1"] - pg)):
        tg = {"door", "doorL" if side == "왼" else "doorR", "plug"}
        A(_box(f"{side}문 단열재", x0, x1, td, td + ti, pz0, pz1,
               "ins", keys={"t_ins", "plug_gap"}, tags=tg,
               bom=("문 단열재", "ins", pz1 - pz0, x1 - x0, ti, "플러그")))
        A(_box(f"{side}문 속판", x0, x1, td + ti, td + ti + tl, pz0, pz1, "cedar", keys={"t_in", "plug_gap"}, tags=tg,
               bom=("문 속판", "cedar", pz1 - pz0, x1 - x0, tl, "플러그")))

    # --- 철물(정면 표시용)
    hw = []
    nh = max(int(p["hinges"]), 1)
    for k in range(nh):
        zc = dz0 + 60 + (doorh - 120) * (k / (nh - 1) if nh > 1 else 0.5)
        for x in (t, W - t):
            hw.append(("경첩", x, zc))
    d["hardware"] = hw
    d["door_z"] = (dz0, dz1)

    # --- 열원
    if p["heat"] == "film":
        fm_, fwmax = p["film_margin"], p["film_w"]
        fl = []
        def film(nm, a, b):
            # a: 가로(폭 방향 후보), b: 세로 → 폭은 film_w 이하
            wa, wb = a - 2 * fm_, b - 2 * fm_
            if wa <= 0 or wb <= 0:
                return None
            c1 = (min(wa, fwmax), wb)
            c2 = (min(wb, fwmax), wa)
            w1, l1 = max(c1, c2, key=lambda c: c[0] * c[1])
            return (nm, w1, l1)
        fc = faces()
        e = 1.0
        if "뒤" in fc:
            fl.append(film("뒤", a1 - a0 - 2 * tl, zt1 - zf - 2 * (ti + tl)))
            A(_box("필름(뒤)", a0 + tl + fm_, a1 - tl - fm_, b1 - e, b1, zf + ti + tl + fm_, zt1 - ti - tl - fm_, "film", tags={"film"}, keys={"film_w", "film_margin", "film_faces"}))
        if "위" in fc:
            fl.append(film("위", a1 - a0, b1 - yfront))
            A(_box("필름(위)", a0 + fm_, a1 - fm_, yfront + fm_, b1 - fm_, zt1 - ti - e, zt1 - ti, "film", tags={"film"}, keys={"film_w", "film_margin", "film_faces"}))
        if "아래" in fc:
            fl.append(film("아래", a1 - a0, b1 - yfront))
            A(_box("필름(아래)", a0 + fm_, a1 - fm_, yfront + fm_, b1 - fm_, zf + ti, zf + ti + e, "film", tags={"film"}, keys={"film_w", "film_margin", "film_faces"}))
        for nm, x in (("좌", a0), ("우", a1 - e)):
            if nm in fc:
                fl.append(film(nm, b1 - yfront, zt1 - zf - 2 * (ti + tl)))
                A(_box(f"필름({nm})", x, x + e, yfront + fm_, b1 - fm_, zf + ti + tl + fm_, zt1 - ti - tl - fm_, "film", tags={"film"}, keys={"film_w", "film_margin", "film_faces"}))
        d["films"] = [x for x in fl if x]
        d["power"] = sum(w * l for _, w, l in d["films"]) / 1e6 * p["film_wpm2"]
    else:
        bd, bh = p["bulb_d"], p["bulb_h"]
        yc = (d["cy0"] + d["cy1"]) / 2
        A(_box("적외선 전구", xm - bd / 2, xm + bd / 2, yc - bd / 2, yc + bd / 2, d["cz0"], d["cz0"] + bh, "bulb",
               tags={"bulb"}, keys={"bulb_d", "bulb_h", "bulb_watt"}, shape="bulb"))
        d["films"] = []
        d["power"] = p["bulb_watt"]

    # --- 거치대
    rt, L, yb_in = d["rack_top"], d["rack_len"], d["cy1"]
    rk = {"rack", "rack_drop", "rack_gap", "rack_back", "n_bows", "bow_pitch"}
    if p["rack"] == "1":
        prof = rack1_profile(L)
        for sgn in (-1, 1):
            xc = xm + sgn * p["rack_gap"] / 2
            A(_box("삼각 받침", xc - p["r1_w"] / 2, xc + p["r1_w"] / 2, yb_in - L, yb_in, rt - p["r1_h"], rt + p["r1_lip"],
                   "ply", keys=rk | {"r1_w", "r1_h", "r1_tip", "r1_lip"}, tags={"rack"},
                   prof=[(yb_in - u, rt - p["r1_h"] + v) for u, v in prof],
                   bom=("삼각 받침", "ply", L, p["r1_h"] + p["r1_lip"], p["r1_w"], "형판: 상세도 1:1"),
                   dev=[(u, v) for u, v in prof]))
        d["supports"] = [(-p["rack_gap"] / 2, rt), (p["rack_gap"] / 2, rt)]
    elif p["rack"] == "2":
        dd = p["r2_d"]
        for sgn in (-1, 1):
            xc = xm + sgn * p["rack_gap"] / 2
            ins_ = tl + ti + 12
            A(_box("둥근 막대", xc - dd / 2, xc + dd / 2, yb_in - L, yb_in + ins_, rt - dd, rt, "ply",
                   keys=rk | {"r2_d"}, tags={"rack"}, shape="cyl",
                   bom=("둥근 막대", "ply", L + ins_, dd, dd, f"Ø{dd:g}, 속판·단열재 관통 + 뒷판 12 박음")))
        d["supports"] = [(-p["rack_gap"] / 2, rt), (p["rack_gap"] / 2, rt)]
    else:
        a, cw, chh = p["r3_arm"], p["r3_cap_w"], p["r3_cap_h"]
        A(_box("줌걸이 각재", xm - a / 2, xm + a / 2, yb_in - L, yb_in, rt - chh - a, rt - chh, "ply",
               keys=rk | {"r3_arm"}, tags={"rack"}, bom=("줌걸이 각재", "ply", L, a, a, "뒷판까지 볼트")))
        A(_box("줌 받침", xm - cw / 2, xm + cw / 2, yb_in - L, yb_in - p["rack_back"] + 5, rt - chh, rt, "ply",
               keys=rk | {"r3_cap_w", "r3_cap_h"}, tags={"rack"}, bom=("줌 받침", "ply", L - p["rack_back"] + 5, cw, chh, "윗면 R 다듬기")))
        d["supports"] = [(0.0, rt)]
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


# ---------------------------------------------------------------- 부린활 형상
def bow_curves(d, state):
    """state: open(벌어짐) / closed(오므라짐). 반환: [(외곽 x,z), (안쪽 x,z)], 맨 위(외곽) z"""
    p = P()
    lb = p["bow_limb"]
    if state == "open":
        a, h = p["bow_open_span"] / 2, p["bow_open_h"]
        phi = np.linspace(-math.pi / 2, math.pi / 2, 181)
        fx = lambda a_, ph: a_ * np.sin(ph)
        fz = lambda h_, ph: h_ * (1 - np.cos(ph))
    else:
        a, h = p["bow_ring_w"] / 2, p["bow_ring_h"] / 2
        lim = math.pi - math.radians(25)
        phi = np.linspace(-lim, lim, 241)
        fx = lambda a_, ph: a_ * np.sin(ph)
        fz = lambda h_, ph: h_ * (1 - np.cos(ph))
    ai, hi = a - lb, h - lb / (1 if state == "open" else 2)
    # 받침점에서 안쪽 곡선이 닿도록 맨 위 높이 결정
    ztop_in = -1e9
    for xs, zs in d["supports"]:
        s_ = min(abs(xs) / max(ai, 1), 1.0)
        ph = math.asin(s_)
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
        low = d["cz0"]
        bot = zo.min() - low
        if p["heat"] == "bulb":
            bd = p["bulb_d"] / 2 + c
            m = np.abs(xo - d["xm"]) < bd
            if m.any():
                bot = min(bot, zo[m].min() - (d["cz0"] + p["bulb_h"]))
        res.append((f"{nm} 아래 여유", bot, c))
    n = int(p["n_bows"])
    front = d["cy1"] - p["rack_back"] - n * p["bow_pitch"]
    res.append((f"앞쪽 여유 (활 {n}장)", front - d["cy0"], c))
    res.append(("거치대 높이(받침 아래 공간)", d["rack_top"] - d["cz0"], 100.0))
    return [(a, b, cc, b >= cc - 1e-6) for a, b, cc in res]


# ---------------------------------------------------------------- 그리기 도구
A3 = (420.0, 297.0)


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


def draw_front(ax, parts, d, opened):
    """정면도. opened=True면 문을 떼어낸 내부 모습"""
    sel = [q for q in parts if not (opened and "door" in q["tags"])]
    if not opened:   # 문 닫힘: 겉에서 보이는 겉판·문·발만
        sel = [q for q in sel if q["mat"] == "pine" and "rack" not in q["tags"]]
    for q in sorted(sel, key=lambda q: -q["b"][2]):
        if q["mat"] == "gasket" and not opened:
            continue
        if q.get("shape") == "cyl":
            x0, x1, _, _, z0, z1 = q["b"]
            ax.add_patch(Circle(((x0 + x1) / 2, (z0 + z1) / 2), (x1 - x0) / 2, fc=MAT[q["mat"]][1], ec="k", lw=0.5, zorder=3))
            continue
        if q.get("shape") == "bulb":
            x0, x1, _, _, z0, z1 = q["b"]
            xc, r = (x0 + x1) / 2, (x1 - x0) / 2
            ax.add_patch(Rectangle((xc - 25, z0), 50, 60, fc="#bbbbbb", ec="k", lw=0.4, zorder=3))
            th = np.linspace(0, math.pi, 30)
            pts = [(xc - r, z1 - r * 0.8)] + [(xc + r * math.cos(a), z1 - r * 0.8 + r * 0.8 * math.sin(a)) for a in th[::-1]] + [(xc + r, z1 - r * 0.8), (xc + 22, z0 + 60), (xc - 22, z0 + 60)]
            ax.add_patch(Polygon(pts, fc=MAT["bulb"][1], ec="k", lw=0.4, zorder=3))
            continue
        if q["mat"] == "film":
            x0, x1, _, _, z0, z1 = q["b"]
            if x1 - x0 < 3:
                ax.plot([x0, x0], [z0, z1], color=MAT["film"][1], lw=1.2, zorder=4)
            elif z1 - z0 < 3:
                ax.plot([x0, x1], [z0, z0], color=MAT["film"][1], lw=1.2, zorder=4)
            else:
                ax.add_patch(Polygon(proj(q, "front"), fc="none", ec=MAT["film"][1], lw=0.8, ls="--", zorder=2.5))
            continue
        _poly(ax, proj(q, "front"), q["mat"], lw=0.5, z=2)
        for _, xc, w, h in q.get("holes", []):
            zc = (q["b"][4] + q["b"][5]) / 2
            ax.add_patch(Rectangle((xc - w / 2, zc - h / 2), w, h, fc="#333", ec="k", lw=0.4, zorder=3))
    if not opened:
        p = P()
        # 경첩·손잡이·귀장석
        for _, x, zc in d["hardware"]:
            ax.add_patch(Rectangle((x - 22, zc - 45), 44, 90, fc=MAT["steel"][1], ec="k", lw=0.3, zorder=5, alpha=0.9))
        xm = d["xm"]; dz0, dz1 = d["door_z"]
        zc = (dz0 + dz1) / 2
        ax.add_patch(Rectangle((xm - 55, dz1 - 150), 110, 130, fc=MAT["steel"][1], ec="k", lw=0.3, zorder=5, alpha=0.9))
        ax.text(xm, dz1 - 85, "앞바탕", color="w", fontsize=4, ha="center", va="center", zorder=6)
        for sgn in (-1, 1):
            ax.add_patch(Rectangle((xm + sgn * 40 - 6, zc - 50), 12, 100, fc="#6b4b2a", ec="k", lw=0.3, zorder=5))
        W, H = p["W"], p["H"]
        c = 50
        for (x, z, sx, sz) in ((0, H, 1, -1), (W, H, -1, -1), (0, p["foot_h"], 1, 1), (W, p["foot_h"], -1, 1)):
            ax.add_patch(Polygon([(x, z), (x + sx * c, z), (x, z + sz * c)], fc=MAT["steel"][1], ec="k", lw=0.3, zorder=5))


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
    s = pick_scale(2 * (W + 2 * m) + (D + 2 * m), H + D + 4 * m, 380, 235)
    fig, ax0 = new_sheet("조립도", f"양문 여닫이 · 부린활 {int(p['n_bows'])}장 · W{W:g}×H{H:g}×D{D:g}", 1, 5, f"1:{s}")
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
    ax0.text(gx + m / s, y_front + (H + m * 0.6) / s + 11, "정면도 (문 닫힘)", fontsize=8, weight="bold")
    # 정면도(문 열림)
    gx2 = gx + (W + 2 * m) / s + 6
    a2 = view_axes(fig, gx2, y_front, (-m, W + m), (-m * 0.6, H + m * 0.4), s)
    draw_front(a2, parts, d, True)
    draw_bows(a2, d, "front")
    dim(a2, (d["cx0"], d["cz1"]), (d["cx1"], d["cz1"]), 4, f"안 {d['cw']:.0f}")
    dim(a2, (d["cx0"], d["cz0"]), (d["cx0"], d["cz1"]), 4, f"안 {d['ch']:.0f}")
    dim(a2, (d["cx1"], d["rack_top"]), (d["cx1"], d["cz1"]), -4, f"{p['rack_drop']:g}")
    if p["rack"] in ("1", "2"):
        dim(a2, (d["xm"] - p["rack_gap"] / 2, d["rack_top"]), (d["xm"] + p["rack_gap"] / 2, d["rack_top"]), 3, f"{p['rack_gap']:g}", fs=5)
    ax0.text(gx2 + m / s, y_front + (H + m * 0.6) / s + 11, "정면도 (문 떼어냄 · 내부)", fontsize=8, weight="bold")
    # 측단면도
    xc = rack_xcut(d)
    gx3 = gx2 + (W + 2 * m) / s + 6
    a3 = view_axes(fig, gx3, y_front, (-m, D + m), (-m * 0.6, H + m * 0.4), s)
    draw_side(a3, parts, d, xc)
    draw_bows(a3, d, "side")
    dim(a3, (0, H), (D, H), 6, f"{D:g}")
    dim(a3, (d["cy0"], d["cz0"]), (d["cy1"], d["cz0"]), -3, f"안 {d['cd']:.0f}", fs=5)
    ax0.text(gx3 + m / s, y_front + (H + m * 0.6) / s + 11, "측단면도 A-A", fontsize=8, weight="bold")
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
    # 검사 결과
    res = checks(parts, d)
    x, y = gx2 + 4, yp + (D + 2 * m) / s - 4
    ax0.text(x, y, "여유 검사", fontsize=7.5, weight="bold")
    for i, (nm, v, c, ok) in enumerate(res):
        ax0.text(x, y - 4.2 * (i + 1), f"{'○' if ok else '×'} {nm}: {v:.0f} mm (기준 ≥ {c:g})", fontsize=6,
                 color="k" if ok else "#c00000")
    legend(ax0, 22, 40)
    ax0.text(22, 48, f"열원: {'면상필름 ' + ', '.join(faces()) if p['heat'] == 'film' else '적외선 전구'}  ·  "
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
        items.append((b, q["dev"], qty))
    # 큰 판 → 축척 10 기준 배치
    big = [it for it in items if it[0][1] == "pine"]
    s = pick_scale(max(max(np.array(it[1])[:, 0].max() for it in big), 1), 1, 120, 1e9)
    s = max(s, 10)
    fig, ax0 = new_sheet("부재도", "몸체 겉판·문 겉판 전개 (사개 손 포함)", 2, 5, f"1:{s}")
    x, y, rowh = 20, 278, 0
    for b, dev, qty in big:
        pts = np.array(dev, float)
        w, h = pts[:, 0].max() - pts[:, 0].min(), pts[:, 1].max() - pts[:, 1].min()
        # 길이 방향을 가로로
        pw, ph = w / s, h / s
        if x + pw + 25 > 405:
            x, y = 20, y - rowh - 16
            rowh = 0
        a = view_axes(fig, x, y - ph - 6, (pts[:, 0].min() - 10, pts[:, 0].max() + 10), (pts[:, 1].min() - 10, pts[:, 1].max() + 10), s)
        a.add_patch(Polygon(pts, fc=MAT["pine"][1], ec="k", lw=0.6))
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
    ax0.text(20, 46, f"뒷판·중간판은 옆판·천판·지판 안쪽에 홈({p['dado']:g}) 파서 끼움 — 재단표 치수에 홈 깊이 포함.", fontsize=6)
    ax0.text(20, 40, "문 겉판: 왼문 오른쪽 끝 뒤쪽 반, 오른문 왼쪽 끝 앞쪽 반을 턱으로 깎아 겹침(턱맞춤) — 상세도 참조.", fontsize=6)
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
        a.text(-16, p["r1_h"] / 2 + 30, "뒷속판 쪽", rotation=90, fontsize=6, ha="center", va="center")
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
    ax0.text(x0, 100, f"• 활 {int(p['n_bows'])}장 × {p['bow_pitch']:g} (궁대 포함) + 뒤 여유 {p['rack_back']:g} → 길이 {d['rack_len']:.0f}", fontsize=7)
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
    fig, ax0 = new_sheet("밀폐·단열 상세", "문받이 · 양문 턱맞춤 · 가스켓 · 벽 구성", no, total, "1:1")
    zc = (d["door_z"][0] + d["door_z"][1]) / 2
    t, td = p["t"], p["t_door"]
    span = td + d["s"] + 45
    sd = 1
    b1 = view_axes(fig, 30, 165, (-10, span), (-span, 10), sd)
    draw_plan(b1, parts, d, zc)
    ax0.text(30, 165 + (span + 10) / sd + 6, "ⓐ 옆판 앞 모서리 평단면", fontsize=8, weight="bold")
    label(b1, (t / 2, -span + 15), "옆판", (-8, -6))
    label(b1, (t + 40, -td / 2), "문 겉판", (6, 8))
    label(b1, (t + p["t_ins"] / 2, -td - 30), "단열재", (10, -4))
    label(b1, (t + p["t_ins"] + p["t_in"] / 2, -td - 38), "속판", (8, -8))
    label(b1, (t + d["s"] / 2, -td - 1), "가스켓", (16, 2))
    label(b1, (t + d["s"] + 25, -td - 5), "문 플러그", (10, -14))
    xm = d["xm"]
    b2 = view_axes(fig, 140, 165, (xm - 55, xm + 55), (-span, 10), sd)
    draw_plan(b2, parts, d, zc)
    dim(b2, (xm + p["gap"] / 2, -td), (xm + p["rebate"], -td), -4, f"턱 {p['rebate']:g}", fs=5.5)
    dim(b2, (xm - 50, 0), (xm - 50, -td / 2), 4, f"{td / 2:g}", fs=5.5)
    label(b2, (xm + p["rebate"] / 2, -td / 2), "가스켓", (14, 6))
    label(b2, (xm - 30, -td / 4), "왼문", (-6, 8))
    label(b2, (xm + 30, -td / 4), "오른문", (4, 8))
    ax0.text(140, 165 + (span + 10) / sd + 6, "ⓑ 양문 맞닿는 곳 평단면", fontsize=8, weight="bold")
    b3 = view_axes(fig, 30, 45, (-10, span), (p["H"] - span, p["H"] + 10), sd)
    draw_side(b3, parts, d, xm - 100)
    label(b3, (span - 20, p["H"] - t / 2), "천판", (6, 4))
    label(b3, (td / 2, p["H"] - t - 30), "문 겉판", (12, -6))
    ax0.text(30, 45 + (span + 20) / sd + 4, "ⓒ 위 문받이 측단면", fontsize=8, weight="bold")
    zf = d["zf"]
    b4 = view_axes(fig, 140, 45, (-10, span), (zf - 45, zf + span - 35), sd)
    draw_side(b4, parts, d, xm - 100)
    label(b4, (span - 20, zf - t / 2), "중간판", (6, -4))
    ax0.text(140, 45 + (span + 20) / sd + 4, "ⓓ 아래 문받이 측단면", fontsize=8, weight="bold")
    x = 275
    ax0.text(x, 270, "밀폐·단열 구조", fontsize=9, weight="bold")
    notes = [
        f"• 벽(뒤·위·아래·좌·우): 겉판 {t:g} + 단열재 {p['t_ins']:g} + 면상필름 + 삼나무 속판 {p['t_in']:g}",
        f"• 문: 겉판 {td:g} 뒤에 단열 플러그(단열재 {p['t_ins']:g} + 속판 {p['t_in']:g})",
        f"   플러그는 안쪽 공간보다 둘레 {p['plug_gap']:g} 작게 → 문을 닫으면 안으로 들어감",
        f"• 문받이: 단열층 앞 가장자리 둘레(폭 {d['s']:g})에 D형 가스켓 {p['gasket_w']:g}×{p['gasket_h']:g}",
        f"   문받이 면은 문 뒷면에서 {p['gasket_h'] * 0.5:g} 뒤 (가스켓 눌림 50%)",
        f"• 양문: 턱맞춤 {p['rebate']:g} (두께 반씩 깎아 겹침) + 턱에 가스켓",
        "• 앞바탕·고리로 양문을 눌러 닫음",
        f"• 문 둘레 틈 {p['gap']:g}, 경첩은 문 한 짝당 {int(p['hinges'])}개",
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
    r = [("나비경첩", nh * 2, f"문 한 짝당 {nh}"), ("앞바탕·고리", 1, "문 위 가운데"),
         ("문 손잡이", 2, ""), ("귀장석", 4, "앞 모서리"), ("들쇠", 2, "옆판"),
         ("D형 가스켓", 1, f"{p['gasket_w']:g}×{p['gasket_h']:g}, 약 {gasket_len(d) / 1000:.1f} m"),
         ("온도조절기", 1, f"타공 {p['thermo_w']:g}×{p['thermo_h']:g}, 센서는 활 옆 중간 높이")]
    if d["ctl"] > 0:
        r.append(("다이얼(조광·타이머)", 1, f"타공 {p['dial_w']:g}×{p['dial_h']:g}"))
    if p["heat"] == "film":
        for nm, w, l in d["films"]:
            r.append((f"면상필름({nm})", 1, f"{w:.0f}×{l:.0f}"))
    else:
        r.append(("적외선 전구·소켓", 1, f"{p['bulb_watt']:g} W, 철망 덮개"))
    r.append(("전원코드·휴즈", 1, f"합계 약 {d['power']:.0f} W"))
    return r


def gasket_len(d):
    p = P()
    W, t = p["W"], p["t"]
    dz0, dz1 = d["door_z"]
    return 2 * (W - 2 * t) + 2 * (dz1 - dz0) + (dz1 - dz0)


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
        f"문 높이 {d['door_z'][1] - d['door_z'][0]:.0f}, 조절부 안높이 {d['ctl']:g}",
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
        "6. 조절부 칸 뒤쪽은 점검구(나사 고정)로 함.",
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
    if d["rack_len"] > d["cd"]:
        e.append(f"거치대 길이({d['rack_len']:.0f})가 안쪽 깊이({d['cd']:.0f})보다 깁니다. 활 장수를 줄이거나 깊이를 늘리세요.")
    if p["heat"] == "film" and not faces():
        e.append("필름을 붙일 면을 하나 이상 선택하세요.")
    if p["rack"] not in ("1", "2", "3"):
        e.append("거치대 형식은 1, 2, 3 중 하나입니다.")
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
