"""
웹(브라우저, Pyodide) 버전의 파이썬 쪽 연결부.
jeomhwajang_core / jeomhwajang_3d 를 그대로 쓰고, 화면에 필요한 값만 JSON으로 넘긴다.
입력 항목(TABS)과 설명(DESCR)은 데스크톱 GUI 파일에서 읽어 와서 한 곳에서만 관리한다.
"""
import ast
import json
import os
import shutil

import numpy as np
import jeomhwajang_core as core
import jeomhwajang_3d as d3

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = dict(core.PARAM)
OUT = "/out"


def _literal(fn, name):
    """tkinter를 import하지 않고 파일에서 상수(TABS, DESCR 등)만 읽음"""
    with open(os.path.join(HERE, fn), encoding="utf-8") as fp:
        tree = ast.parse(fp.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def _num(v):
    if isinstance(v, (np.floating, np.integer)):
        return v.item()
    return v


def ui():
    """입력 화면 구성: 탭·항목·설명·기본값·면 이름"""
    return json.dumps(dict(
        tabs=_literal("jeomhwajang_gui.py", "TABS"),
        descr=_literal("jeomhwajang_preview.py", "DESCR"),
        defaults=DEFAULTS,
        faces=list(core.FACE_NAMES),
        credit=getattr(core, "CREDIT", ""),
    ), ensure_ascii=False)


def _set(params):
    core.PARAM.clear()
    core.PARAM.update(DEFAULTS)
    core.apply(params or {})


def _extra_errors(params):
    e = []
    try:
        n = float(params.get("n_bows", 1))
        if n < 1 or n != int(n):
            e.append("활 장수는 1 이상의 정수여야 합니다.")
    except (TypeError, ValueError):
        e.append("활 장수가 숫자가 아닙니다.")
    try:
        if float(params.get("mag_n", 1)) not in (1, 2):
            e.append("자석 캐치 수는 1(위) 또는 2(위·아래)입니다.")
    except (TypeError, ValueError):
        e.append("자석 캐치 수가 숫자가 아닙니다.")
    for k, v in params.items():
        if k in core.STR_KEYS:
            continue
        try:
            if float(v) < 0:
                e.append(f"'{k}' 값은 0 이상이어야 합니다.")
        except (TypeError, ValueError):
            e.append(f"'{k}' 값이 숫자가 아닙니다.")
    return e


def preview(params_json):
    """미리보기용 부재·활 곡선·검사 결과"""
    params = json.loads(params_json)
    errs = _extra_errors(params)
    if errs:
        return json.dumps(dict(errors=errs), ensure_ascii=False)
    try:
        _set(params)
        errs = core.validate()
        parts, d = core.build()
    except Exception as ex:  # noqa
        return json.dumps(dict(errors=[f"계산 오류: {ex}"]), ensure_ascii=False)
    P = []
    for q in parts:
        P.append(dict(
            n=q["name"], b=[float(x) for x in q["b"]], m=q["mat"],
            k=sorted(q["keys"]), t=sorted(q["tags"]),
            prof=[[float(a), float(b)] for a, b in q["prof"]] if "prof" in q else None,
            shape=q.get("shape"),
            holes=[[h[0]] + [float(x) for x in h[1:]] for h in q.get("holes", [])],
        ))
    bows = {}
    for st in ("open", "closed"):
        (xo, zo), (xi, zi), zt = core.bow_curves(d, st)
        bows[st] = dict(xo=xo[::3].round(1).tolist(), zo=zo[::3].round(1).tolist(),
                        xi=xi[::3].round(1).tolist(), zi=zi[::3].round(1).tolist(), zt=float(zt),
                        zmin=float(zo.min()))
    D = {k: _num(v) for k, v in d.items() if isinstance(v, (int, float, np.floating, np.integer))}
    D["xcut"] = float(core.rack_xcut(d))
    checks = [[a, float(b), float(c), bool(ok)] for a, b, c, ok in core.checks(parts, d)]
    return json.dumps(dict(parts=P, d=D, bows=bows, checks=checks, errors=errs,
                           P={k: _num(v) for k, v in core.P().items()}), ensure_ascii=False)


def generate(params_json, want3d):
    """도면(PDF·DXF·CSV)과 3D 파일을 /out 에 만들고 파일 경로 목록을 돌려줌"""
    params = json.loads(params_json)
    errs = _extra_errors(params)
    _set(params)
    errs += core.validate()
    if errs:
        return json.dumps(dict(errors=errs), ensure_ascii=False)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    files = core.generate(OUT, params=None)
    if want3d:
        files += d3.export_3d(OUT, params=None)
    parts, d = core.build()
    bad = [[a, float(b), float(c)] for a, b, c, ok in core.checks(parts, d) if not ok]
    return json.dumps(dict(files=files, bad=bad), ensure_ascii=False)
