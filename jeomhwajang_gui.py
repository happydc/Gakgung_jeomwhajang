"""
각궁 점화장 제작도면 생성기 — 윈도우용 GUI
치수를 입력하고 [도면 생성]을 누르면 PDF(A3 5장), DXF(부재 전개 1:1), CSV(재단표)를 만듭니다.
"""
import os
import sys
import json
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import jeomhwajang_core as core
from jeomhwajang_preview import Preview, DESCR

APP_TITLE = "각궁 점화장 제작도면 생성기"
SETTINGS = os.path.join(os.path.expanduser("~"), ".gakgung_jeomhwajang.json")

# 탭: [(키, 라벨, 단위)]
TABS = [
    ("본체", [
        ("W", "외형 가로", "mm"), ("H", "외형 높이", "mm"), ("D", "외형 깊이", "mm"),
        ("t", "겉판 두께", "mm"), ("foot_h", "발 높이", "mm"), ("foot_w", "발 크기", "mm"),
        ("pin_pitch", "사개 손 간격", "mm"), ("dado", "홈 깊이", "mm"),
    ]),
    ("단열·밀폐", [
        ("t_ins", "단열재 두께", "mm"), ("t_in", "속판(삼나무) 두께", "mm"), ("frame_d", "문틀 띠 깊이", "mm"),
        ("gasket_w", "가스켓 폭", "mm"), ("gasket_h", "가스켓 두께", "mm"),
        ("gap", "문 둘레 틈", "mm"), ("plug_gap", "문 플러그 틈", "mm"), ("rebate", "양문 턱 너비", "mm"),
    ]),
    ("문", [
        ("door_h", "문 높이(천판 아래부터)", "mm"), ("t_door", "문 겉판 두께", "mm"), ("hinges", "경첩 수(한 짝)", "개"),
        ("mag_n", "자석 캐치 수(한 짝, 1~2)", "개"), ("mag_d", "자석 지름", "mm"), ("mag_off", "자석: 가운데→거리", "mm"),
    ]),
    ("하부·전원", [
        ("lower_h", "하부 공간 안높이", "mm"), ("shelf_t", "선반 두께", "mm"), ("cleat", "선반받이 각재", "mm"),
        ("vent_w", "통풍 슬롯 폭", "mm"), ("vent_pitch", "통풍 슬롯 간격", "mm"),
        ("thermo_w", "온도조절기 홀 가로", "mm"), ("thermo_h", "온도조절기 홀 세로", "mm"), ("thermo_x", "옆판→온도조절기 홀", "mm"),
        ("recp_w", "리셉터클 타공 가로", "mm"), ("recp_h", "리셉터클 타공 세로", "mm"), ("recp_pitch", "리셉터클 나사 간격", "mm"),
        ("recp_hole", "리셉터클 나사 구멍", "mm"), ("recp_x", "옆판→리셉터클 타공", "mm"), ("set_temp", "설정 온도", "℃"),
    ]),
    ("열원", [
        ("film_w", "필름 최대 폭", "mm"), ("film_margin", "필름 여유", "mm"), ("film_wpm2", "필름 전력", "W/m²"),
        ("ptc_w", "PTC 가로", "mm"), ("ptc_d", "PTC 깊이", "mm"), ("ptc_h", "PTC 높이", "mm"), ("ptc_watt", "PTC 전력", "W"),
    ]),
    ("거치대", [
        ("rack_drop", "속 천장→거치대 윗면", "mm"), ("rack_gap", "받침 중심 간격", "mm"),
        ("rack_back", "뒤 여유", "mm"), ("rack_front", "앞끝→문 안쪽 면", "mm"), ("rack_r", "활 닿는 부분 R", "mm"),
        ("r1_w", "① 받침 폭", "mm"), ("r1_h", "① 받침 높이", "mm"),
        ("r1_tip", "① 끝 두께", "mm"), ("r1_lip", "① 끝 턱 높이", "mm"), ("r2_d", "② 막대 지름", "mm"),
        ("r3_arm", "③ 각재 단면", "mm"), ("r3_cap_w", "③ 받침 폭", "mm"), ("r3_cap_h", "③ 받침 높이", "mm"),
    ]),
    ("부린활", [
        ("n_bows", "활 장수", "장"), ("bow_pitch", "활 1장 두께(궁대 포함)", "mm"),
        ("bow_open_span", "벌어진 활 고자~고자", "mm"), ("bow_open_h", "벌어진 활 높이", "mm"),
        ("bow_ring_w", "오므라든 활 가로", "mm"), ("bow_ring_h", "오므라든 활 세로", "mm"),
        ("bow_limb", "활채 너비", "mm"), ("clear", "최소 여유", "mm"),
    ]),
]
NUM_KEYS = [k for _, fs in TABS for k, _, _ in fs]
LABELS = {k: l for _, fs in TABS for k, l, _ in fs}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            self._icon = tk.PhotoImage(file=os.path.join(base, "assets", "icon.png"))
            self.iconphoto(True, self._icon)
        except Exception:
            pass
        self.resizable(False, False)
        try:
            self.option_add("*Font", ("Malgun Gothic", 10))
        except Exception:
            pass
        self.defaults = dict(core.PARAM)
        self.vars = {}
        self._build()
        self._load()
        self._refresh()

    # ---------------------------------------------------------------- 화면
    def _build(self):
        pad = dict(padx=6, pady=3)
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True)
        for title, fields in TABS:
            fr = ttk.Frame(nb)
            nb.add(fr, text=title)
            nrow = 8
            for i, (k, lab, unit) in enumerate(fields):
                rr, cc = i % nrow, (i // nrow) * 3
                la = ttk.Label(fr, text=lab)
                la.grid(row=rr, column=cc, sticky="e", **pad)
                v = tk.StringVar(value=f"{core.PARAM[k]:g}")
                en = ttk.Entry(fr, textvariable=v, width=8, justify="right")
                en.grid(row=rr, column=cc + 1, **pad)
                ttk.Label(fr, text=unit).grid(row=rr, column=cc + 2, sticky="w", padx=(0, 10))
                self.vars[k] = v
                self._hover(k, la, en)
                en.bind("<FocusOut>", lambda e: self._refresh(), add="+")
                en.bind("<Return>", lambda e: self._refresh(), add="+")
            r = min(len(fields), nrow)
            if title == "단열·밀폐":
                self.gasket = tk.BooleanVar(value=core.gasket_on())
                cb = ttk.Checkbutton(fr, text="가스켓 사용", variable=self.gasket, command=self._refresh)
                cb.grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=6)
                self._hover("gasket", cb)
            if title == "하부·전원":
                self.side = tk.StringVar(value=core.PARAM["ctl_side"])
                sf = ttk.LabelFrame(fr, text="온도조절기·리셉터클 위치")
                sf.grid(row=r, column=0, columnspan=6, sticky="ew", padx=6, pady=6)
                for val, txt in (("L", "왼쪽"), ("R", "오른쪽")):
                    ttk.Radiobutton(sf, text=txt, value=val, variable=self.side, command=self._refresh).pack(side="left", padx=6)
                self._hover("ctl_side", sf)
            if title == "열원":
                self.heat = tk.StringVar(value=core.PARAM["heat"])
                hf = ttk.LabelFrame(fr, text="열원 종류")
                hf.grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=6)
                for val, txt in (("film", "면상필름"), ("ptc", "PTC 히터(하부 바닥)")):
                    ttk.Radiobutton(hf, text=txt, value=val, variable=self.heat, command=self._refresh).pack(side="left", padx=6)
                self._hover("heat", hf)
                ff = ttk.LabelFrame(fr, text="필름 붙일 면")
                ff.grid(row=r + 1, column=0, columnspan=3, sticky="ew", padx=6, pady=4)
                self.face_vars = {}
                cur = core.faces()
                for nm in core.FACE_NAMES:
                    b = tk.BooleanVar(value=nm in cur)
                    ttk.Checkbutton(ff, text=nm, variable=b, command=self._refresh).pack(side="left", padx=4)
                    self.face_vars[nm] = b
                self._hover("film_faces", ff)
            if title == "거치대":
                self.rack = tk.StringVar(value=core.PARAM["rack"])
                rf = ttk.LabelFrame(fr, text="거치대 형식")
                rf.grid(row=r, column=0, columnspan=3, sticky="ew", padx=6, pady=6)
                for val, txt in (("1", "① 삼각 받침 2개"), ("2", "② 둥근 막대 2개"), ("3", "③ 줌걸이 1개")):
                    ttk.Radiobutton(rf, text=txt, value=val, variable=self.rack, command=self._refresh).pack(anchor="w", padx=6)
                self._hover("rack", rf)

        right = ttk.LabelFrame(self, text="미리보기 — 항목에 마우스를 올려 보세요")
        right.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(0, 8), pady=8)
        self.preview = Preview(right)
        self.preview.pack(padx=6, pady=(6, 2))
        self.desc = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.desc, foreground="#7a2020", wraplength=590).pack(anchor="w", padx=8, pady=(0, 6))

        bot = ttk.Frame(left)
        bot.pack(fill="x", pady=(8, 0))
        ttk.Label(bot, text="저장 폴더").grid(row=0, column=0, sticky="w")
        self.outdir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Documents", "점화장도면"))
        ttk.Entry(bot, textvariable=self.outdir, width=34).grid(row=0, column=1, padx=4)
        ttk.Button(bot, text="찾기…", command=self._browse).grid(row=0, column=2)
        bf = ttk.Frame(left)
        bf.pack(fill="x", pady=(8, 0))
        self.btn = ttk.Button(bf, text="도면 생성", command=self._run)
        self.btn.pack(side="left")
        ttk.Button(bf, text="기본값", command=self._reset).pack(side="left", padx=6)
        self.status = tk.StringVar(value="치수를 확인하고 [도면 생성]을 누르세요.")
        ttk.Label(left, textvariable=self.status, foreground="#555", wraplength=330).pack(anchor="w", pady=(6, 0))

    def _hover(self, key, *widgets):
        for w in widgets:
            w.bind("<Enter>", lambda e, k=key: self._show(k), add="+")
            w.bind("<FocusIn>", lambda e, k=key: self._show(k), add="+")
            w.bind("<Leave>", lambda e: self._leave(), add="+")

    def _show(self, k):
        self.preview.show(k)
        self.desc.set(DESCR.get(k, ""))

    def _leave(self):
        self.preview.clear()
        self.desc.set("")

    # ---------------------------------------------------------------- 값
    def _params(self, strict=False):
        p = {}
        for k in NUM_KEYS:
            try:
                p[k] = float(self.vars[k].get())
            except ValueError:
                if strict:
                    raise ValueError(f"'{LABELS[k]}' 값이 숫자가 아닙니다.")
                continue
            if strict and p[k] < 0:
                raise ValueError(f"'{LABELS[k]}' 값은 0 이상이어야 합니다.")
        p["heat"] = self.heat.get()
        p["rack"] = self.rack.get()
        p["gasket"] = "1" if self.gasket.get() else "0"
        p["ctl_side"] = self.side.get()
        p["film_faces"] = ",".join(n for n, b in self.face_vars.items() if b.get())
        return p

    def _refresh(self):
        try:
            self.preview.refresh(self._params())
        except Exception:
            pass

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.outdir.get() or os.path.expanduser("~"))
        if d:
            self.outdir.set(d)

    def _reset(self):
        for k, v in self.vars.items():
            v.set(f"{self.defaults[k]:g}")
        self.heat.set(self.defaults["heat"])
        self.rack.set(self.defaults["rack"])
        self.gasket.set(str(self.defaults["gasket"]) == "1")
        self.side.set(self.defaults["ctl_side"])
        cur = [f.strip() for f in self.defaults["film_faces"].split(",")]
        for n, b in self.face_vars.items():
            b.set(n in cur)
        self._refresh()

    def _run(self):
        try:
            params = self._params(strict=True)
            if params["n_bows"] < 1 or params["n_bows"] != int(params["n_bows"]):
                raise ValueError("활 장수는 1 이상의 정수여야 합니다.")
            if params["mag_n"] not in (1, 2):
                raise ValueError("자석 캐치 수는 1(위) 또는 2(위·아래)입니다.")
            core.apply(params)
            errs = core.validate()
            if errs:
                raise ValueError("\n".join(errs))
        except ValueError as e:
            messagebox.showwarning(APP_TITLE, str(e))
            return
        parts, d = core.build()
        bad = [c for c in core.checks(parts, d) if not c[3]]
        if bad and not messagebox.askyesno(APP_TITLE, "여유가 부족한 항목이 있습니다.\n\n"
                                           + "\n".join(f"• {c[0]}: {c[1]:.0f} mm (기준 {c[2]:g})" for c in bad)
                                           + "\n\n그래도 도면을 만들까요?"):
            return
        out = self.outdir.get().strip() or "."
        self.btn.state(["disabled"])
        self.status.set("생성 중…")

        def work():
            try:
                files = core.generate(out, params=params)
                self.after(0, lambda: self._done(out, files))
            except Exception as e:  # noqa
                self.after(0, lambda: self._fail(e))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, out, files):
        self.btn.state(["!disabled"])
        self.status.set(f"완료: {len(files)}개 파일")
        self._save()
        if messagebox.askyesno(APP_TITLE, "도면을 만들었습니다.\n\n" + "\n".join(os.path.basename(f) for f in files)
                               + "\n\n저장 폴더를 열까요?"):
            if sys.platform.startswith("win"):
                os.startfile(out)  # noqa
            else:
                subprocess.Popen(["xdg-open", out])

    def _fail(self, e):
        self.btn.state(["!disabled"])
        self.status.set("오류")
        messagebox.showerror(APP_TITLE, f"도면 생성 중 오류가 났습니다.\n\n{e}")

    def _save(self):
        try:
            data = {"params": {k: v.get() for k, v in self.vars.items()},
                    "heat": self.heat.get(), "rack": self.rack.get(),
                    "gasket": self.gasket.get(), "ctl_side": self.side.get(),
                    "faces": [n for n, b in self.face_vars.items() if b.get()],
                    "outdir": self.outdir.get()}
            with open(SETTINGS, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _load(self):
        try:
            with open(SETTINGS, encoding="utf-8") as fp:
                data = json.load(fp)
            for k, v in data.get("params", {}).items():
                if k in self.vars:
                    self.vars[k].set(v)
            if data.get("heat"):
                self.heat.set(data["heat"])
            if data.get("rack"):
                self.rack.set(data["rack"])
            if "gasket" in data:
                self.gasket.set(bool(data["gasket"]))
            if data.get("ctl_side") in ("L", "R"):
                self.side.set(data["ctl_side"])
            if data.get("heat") not in ("film", "ptc"):
                self.heat.set("film")
            if "faces" in data:
                for n, b in self.face_vars.items():
                    b.set(n in data["faces"])
            if data.get("outdir"):
                self.outdir.set(data["outdir"])
        except Exception:
            pass


if __name__ == "__main__":
    App().mainloop()
