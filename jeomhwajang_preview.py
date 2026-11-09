"""
입력 화면 미리보기: 내부 정면도(문 떼어냄) + 측단면도.
항목에 마우스를 올리면 해당 부재·치수를 빨간색으로 표시
"""
import tkinter as tk
import numpy as np
import jeomhwajang_core as core

HL = "#d62828"

DESCR = {
    "W": "외형 가로 — 옆판 바깥에서 바깥까지",
    "H": "외형 높이 — 바닥(발 아래)에서 천판 위까지",
    "D": "외형 깊이 — 문 겉판 앞면에서 뒷판 뒷면까지",
    "t": "겉판 두께 — 옆판·천판·지판·뒷판·아래 앞판",
    "foot_h": "발 높이 — 0이면 발 없음",
    "foot_w": "발 크기 — 네 모서리 정사각 발",
    "pin_pitch": "사개 손 간격 — 깊이를 홀수 구간으로 나눌 때의 목표 간격",
    "dado": "홈 깊이 — 뒷판·아래 앞판을 끼우는 홈",
    "t_ins": "단열재 두께 — 겉판과 필름 사이",
    "t_in": "속판 두께 — 삼나무 안쪽 판(필름을 덮음)",
    "frame_d": "문틀 띠 깊이 — 단열층 앞 둘레 원목 띠, 문이 닿고 자석이 박히는 곳",
    "gasket": "가스켓 사용 — 끄면 문이 문틀 띠에 바로 닿음",
    "gasket_w": "가스켓 폭",
    "gasket_h": "가스켓 두께 — 절반 눌린다고 보고 문틀 띠 위치를 정함",
    "gap": "문 둘레 틈 — 문 겉판과 옆판·천판 사이",
    "plug_gap": "플러그 틈 — 문 뒤 단열 플러그와 문틀 띠 사이",
    "rebate": "턱 너비 — 양문이 겹치는 턱맞춤 너비",
    "door_type": "문 형식 — 양문 여닫이 / 반닫이(문판 한 장이 아래 끝 경첩으로 앞으로 젖혀 열림)",
    "bj_cleat": "반닫이 문판 양끝 마구리 폭 — 세로결 띠로 문판 휨 방지(0이면 통판)",
    "bj_hinges": "반닫이 경첩 수 — 문판 아래 끝, 축이 앞면 선",
    "bj_stays": "반닫이 지지대 수 — 문판을 90°에서 받쳐 작업 선반처럼 씀",
    "door_h": "문 높이 — 천판 아래에서 아래로. 그 아래는 고정된 아래 앞판",
    "t_door": "문 겉판 두께",
    "hinges": "경첩 수 — 문 한 짝당",
    "mag_n": "자석 캐치 수 — 문 한 짝당 1(위) 또는 2(위·아래)",
    "mag_d": "자석 지름 — 문틀 띠에 매립",
    "mag_off": "자석 위치 — 가운데(양문 맞닿는 곳)에서 좌우 거리",
    "lower_h": "하부 공간 안높이 — 속 바닥에서 선반 아랫면까지. 선반 윗면이 문 하단보다 높으면 오류",
    "shelf_t": "선반 두께 — 착탈식, 통풍 슬롯",
    "cleat": "선반받이 각재 — 옆속판에 붙여 선반을 얹음",
    "vent_w": "통풍 슬롯 폭", "vent_pitch": "통풍 슬롯 간격",
    "ctl_side": "온도조절기(아래 앞판)·리셉터클(뒷판 아래) 위치",
    "thermo_w": "온습도 조절기 몸체 타공 가로 — 실물 몸체에 맞춤", "thermo_h": "온습도 조절기 몸체 타공 세로",
    "bezel_w": "조절기 앞 테두리 가로(XM-18: 160)", "bezel_h": "조절기 앞 테두리 세로(XM-18: 80)",
    "ctl_depth": "조절기 깊이 — 테두리 포함(XM-18: 89)",
    "thermo_x": "옆판 바깥 → 조절기 앞 테두리 가장자리",
    "recp_w": "리셉터클(IEC 인렛) 몸체 타공 가로 — 수평 배치", "recp_h": "리셉터클 몸체 타공 세로",
    "recp_pitch": "리셉터클 나사 구멍 좌우 간격", "recp_hole": "리셉터클 나사 구멍 지름",
    "recp_x": "옆판 바깥 → 리셉터클 타공 가장자리(덮개 젖힘 여유 포함)",
    "set_temp": "설정 온도 — 도면 주기에만 표시",
    "heat": "열원 — 면상필름 또는 PTC 히터(하부 바닥)",
    "film_faces": "필름 붙일 면",
    "film_w": "필름 최대 폭 — 롤 폭",
    "film_margin": "필름 여유 — 속판 가장자리에서 띄우는 거리",
    "film_wpm2": "필름 소비전력 — 1 m²당 W",
    "ptc_w": "PTC 히터 가로", "ptc_d": "PTC 히터 깊이", "ptc_h": "PTC 히터 높이", "ptc_watt": "PTC 히터 전력",
    "rack": "거치대 형식 — ① 삼각 받침 2 / ② 둥근 막대 2 / ③ 줌걸이 1",
    "rack_drop": "거치대 높이 — 속 천장에서 거치대 윗면까지",
    "rack_gap": "거치대 간격 — 두 받침(막대)의 중심 간격",
    "rack_back": "뒤 여유 — 뒷속판과 첫 활 사이",
    "rack_front": "앞끝 여유 — 거치대 앞끝과 문 안쪽 면(플러그) 사이",
    "rack_r": "라운드 R — 활 닿는 모서리",
    "r1_w": "삼각 받침 폭(두께)", "r1_h": "삼각 받침 높이(뒷면)", "r1_tip": "삼각 받침 끝 두께", "r1_lip": "삼각 받침 끝 턱 높이",
    "r2_d": "둥근 막대 지름",
    "r3_arm": "줌걸이 각재 단면", "r3_cap_w": "줌 받침 폭", "r3_cap_h": "줌 받침 높이",
    "n_bows": "활 장수 — 깊이 방향으로 나란히 걺",
    "bow_pitch": "활 1장 두께 — 궁대 포함",
    "bow_open_span": "벌어진 부린활 — 고자~고자 최대 폭",
    "bow_open_h": "벌어진 부린활 — 줌통 위에서 고자까지 높이",
    "bow_ring_w": "오므라든 부린활 — 바깥 가로",
    "bow_ring_h": "오므라든 부린활 — 바깥 세로",
    "bow_limb": "활채 너비 — 정면에서 보이는 활 두께",
    "clear": "최소 여유 — 활과 벽 사이 기준",
}

BOW_KEYS = {"bow_open_span", "bow_open_h", "bow_ring_w", "bow_ring_h", "bow_limb", "clear", "n_bows", "bow_pitch"}


class Preview(tk.Canvas):
    W, H = 600, 430

    def __init__(self, master, **kw):
        super().__init__(master, width=self.W, height=self.H, bg="#fbf8f2",
                         highlightthickness=1, highlightbackground="#d8d0c2", **kw)
        self.key = None
        self.parts, self.d = None, None
        self.refresh()

    def refresh(self, params=None):
        try:
            if params:
                core.apply(params)
            self.parts, self.d = core.build()
        except Exception:
            if self.parts is None:
                return
        self._draw()

    def show(self, key):
        self.key = key
        self._draw()

    def clear(self):
        self.key = None
        self._draw()

    def _hl(self, q):
        k = self.key
        if not k:
            return False
        if k in q["keys"]:
            return True
        if k == "heat" and q["mat"] in ("film", "ptc"):
            return True
        return False

    def _draw(self):
        self.delete("all")
        if not self.parts:
            return
        p, d, parts = core.P(), self.d, self.parts
        Wm, Hm, Dm = p["W"], p["H"], p["D"]
        s = min(330 / Wm, 360 / Hm, 170 / Dm)
        ox, oy = 30, 395
        fx = lambda x: ox + x * s
        fz = lambda z: oy - z * s
        # 정면(문 떼어냄)
        for q in sorted(parts, key=lambda q: -q["b"][2]):
            if "door" in q["tags"] or "lowfront" in q["tags"]:
                continue
            x0, x1, y0, y1, z0, z1 = q["b"]
            hl = self._hl(q)
            col = core.MAT[q["mat"]][1]
            if q["mat"] == "film":
                if x1 - x0 < 3:
                    self.create_line(fx(x0), fz(z0), fx(x0), fz(z1), fill=HL if hl else "#e03030", width=3 if hl else 2)
                elif z1 - z0 < 3:
                    self.create_line(fx(x0), fz(z0), fx(x1), fz(z0), fill=HL if hl else "#e03030", width=3 if hl else 2)
                else:
                    self.create_rectangle(fx(x0), fz(z1), fx(x1), fz(z0), outline=HL if hl else "#e03030", dash=(4, 3), width=2 if hl else 1)
                continue
            if q.get("shape") == "cyl":
                r = (x1 - x0) / 2 * s
                cx, cz = fx((x0 + x1) / 2), fz((z0 + z1) / 2)
                self.create_oval(cx - r, cz - r, cx + r, cz + r, fill=HL if hl else col, outline="#333")
                continue
            if q.get("shape") == "disc":
                r = (x1 - x0) / 2 * s
                cx, cz = fx((x0 + x1) / 2), fz((z0 + z1) / 2)
                self.create_oval(cx - r - 1, cz - r - 1, cx + r + 1, cz + r + 1, fill=HL if hl else "#444", outline="")
                continue
            if "front" in q["tags"]:      # 아래 앞판: 윤곽만
                self.create_rectangle(fx(x0), fz(z1), fx(x1), fz(z0), outline=HL if hl else "#6b5535",
                                      width=2 if hl else 1, dash=(3, 2))
            elif "back" not in q["tags"]:
                self.create_rectangle(fx(x0), fz(z1), fx(x1), fz(z0), fill=HL if hl else col,
                                      outline=HL if hl else "#6b5535", width=2 if hl else 1)
            for kind, xc, zc, w, h in q.get("holes", []):
                hk = self.key in ("ctl_side",) or (self.key or "").startswith(("thermo", "bezel", "ctl_depth") if kind == "thermo" else "recp")
                self.create_rectangle(fx(xc - w / 2), fz(zc + h / 2), fx(xc + w / 2), fz(zc - h / 2),
                                      outline=HL if hk else "#333", width=2 if hk else 1,
                                      fill="" if kind == "recp" else ("#ffd0d0" if hk else "#cfc6b8"), dash=(2, 2) if kind == "recp" else ())
        # 부린활
        bh = self.key in BOW_KEYS
        for st, col, dash in (("open", "#1f5fbf", (5, 3)), ("closed", "#2e8b57", (2, 2))):
            (xo, zo), (xi, zi), _ = core.bow_curves(d, st)
            for xs, zs, w in ((xo, zo, 2), (xi, zi, 1)):
                pts = [c for x, z in zip(xs[::4], zs[::4]) for c in (fx(x), fz(z))]
                self.create_line(*pts, fill=HL if bh else col, dash=dash, width=w + (1 if bh else 0), smooth=True)
        # 외형 치수
        self._dim(fx(0), fz(Hm) - 10, fx(Wm), fz(Hm) - 10, f"{Wm:g}", self.key == "W")
        self._dim(fx(0) - 12, fz(0), fx(0) - 12, fz(Hm), f"{Hm:g}", self.key == "H", vertical=True)
        # 측단면
        sx0 = 400
        gy = lambda y: sx0 + y * s
        xc = core.rack_xcut(d)
        for q in parts:
            x0, x1, y0, y1, z0, z1 = q["b"]
            if not (x0 <= xc <= x1):
                continue
            hl = self._hl(q)
            col = core.MAT[q["mat"]][1]
            if "prof" in q:
                pts = [c for y, z in q["prof"] for c in (gy(y), fz(z))]
                self.create_polygon(*pts, fill=HL if hl else col, outline="#333")
                continue
            if q["mat"] == "film":
                if y1 - y0 < 3:
                    self.create_line(gy(y0), fz(z0), gy(y0), fz(z1), fill=HL if hl else "#e03030", width=2)
                else:
                    self.create_line(gy(y0), fz(z0), gy(y1), fz(z0), fill=HL if hl else "#e03030", width=2)
                continue
            self.create_rectangle(gy(y0), fz(z1), gy(y1), fz(z0), fill=HL if hl else col,
                                  outline=HL if hl else "#6b5535", width=2 if hl else 1)
        (xo, zo), _, zt = core.bow_curves(d, "open")
        for k in range(int(p["n_bows"])):
            yc = d["cy1"] - p["rack_back"] - p["bow_pitch"] * (k + 0.5)
            w = p["bow_pitch"] * 0.8
            self.create_rectangle(gy(yc - w / 2), fz(zt), gy(yc + w / 2), fz(zo.min()),
                                  outline=HL if bh else "#1f5fbf", dash=(4, 2), width=2 if bh else 1)
        self._dim(gy(0), fz(Hm) - 10, gy(Dm), fz(Hm) - 10, f"{Dm:g}", self.key == "D")
        self.create_text(fx(0), 14, anchor="w", text="정면 (문 떼어냄)", font=("Malgun Gothic", 9, "bold"), fill="#444")
        self.create_text(gy(0), 14, anchor="w", text="측단면", font=("Malgun Gothic", 9, "bold"), fill="#444")
        # 검사 결과
        bad = [c for c in core.checks(parts, d) if not c[3]]
        errs = core.validate()
        if errs:
            bad = []
        msg = ("오류: " + errs[0]) if errs else ("여유 검사: 모두 통과" if not bad else "여유 부족: " + ", ".join(f"{c[0]} {c[1]:.0f}" for c in bad))
        self.create_text(10, self.H - 12, anchor="w", text=msg[:95], fill="#2a7a2a" if not (bad or errs) else HL,
                         font=("Malgun Gothic", 9))

    def _dim(self, x1, y1, x2, y2, txt, hl, vertical=False):
        c = HL if hl else "#555"
        self.create_line(x1, y1, x2, y2, arrow="both", arrowshape=(6, 7, 2), fill=c, width=2 if hl else 1)
        if vertical:
            self.create_text(x1 - 4, (y1 + y2) / 2, text=txt, angle=90, fill=c, font=("Malgun Gothic", 8))
        else:
            self.create_text((x1 + x2) / 2, y1 - 7, text=txt, fill=c, font=("Malgun Gothic", 8))
