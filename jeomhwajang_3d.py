"""
점화장 3D 모델: 부재별 삼각형 메시 → OBJ(+MTL), DAE(SketchUp 가져오기용), 3D 뷰어(HTML, 인터넷 없이 열림)
  python jeomhwajang_3d.py    → output 폴더에 기본값으로 생성
좌표: x 왼→오, y 앞→뒤, z 위 (mm). DAE는 Z_UP·밀리미터 단위로 저장.
"""
import os
import sys
import json
import math
import base64
import numpy as np
import jeomhwajang_core as core

# ---------------------------------------------------------------- 기본 도형
def box_mesh(x0, x1, y0, y1, z0, z1):
    V = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    F = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                  [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], int)
    return V, F


def merge(meshes):
    Vs, Fs, n = [], [], 0
    for V, F in meshes:
        if len(V) == 0:
            continue
        Vs.append(V); Fs.append(F + n); n += len(V)
    if not Vs:
        return np.zeros((0, 3)), np.zeros((0, 3), int)
    return np.vstack(Vs), np.vstack(Fs)


def _area2(poly):
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return a


def triangulate(poly):
    """단순 다각형 귀 자르기 → 삼각형 인덱스"""
    pts = [tuple(p) for p in poly]
    idx = list(range(len(pts)))
    if _area2(pts) < 0:
        idx.reverse()
    tris = []

    def inside(p, a, b, c):
        def s(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = s(p, a, b), s(p, b, c), s(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = pts[i0], pts[i1], pts[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:
                continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def extrude(poly, axis, a0, a1):
    """2D 다각형(u,v)을 axis 방향으로 a0~a1 만큼 밀어냄. axis='x': (u,v)=(y,z), 'y': (x,z), 'z': (x,y)"""
    poly = [tuple(p) for p in poly]
    n = len(poly)
    tris = triangulate(poly)
    if _area2(poly) < 0:
        poly = poly[::-1]
        tris = [(n - 1 - i, n - 1 - j, n - 1 - k) for i, j, k in tris]

    def P3(u, v, a):
        if axis == "x":
            return (a, u, v)
        if axis == "y":
            return (u, a, v)
        return (u, v, a)
    V = [P3(u, v, a0) for u, v in poly] + [P3(u, v, a1) for u, v in poly]
    F = []
    for i, j, k in tris:
        F.append((i, k, j))
        F.append((n + i, n + j, n + k))
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j))
        F.append((i, n + j, n + i))
    V, F = np.array(V, float), np.array(F, int)
    # axis에 따라 손잡이 방향이 바뀌므로 법선을 바깥으로 맞춤
    c = V.mean(axis=0)
    fc = V[F].mean(axis=1)
    nrm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if np.sum(np.einsum("ij,ij->i", nrm, fc - c)) < 0:
        F = F[:, [0, 2, 1]]
    return V, F


def circle(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def box_with_holes(b, holes):
    """y 방향 관통 사각 구멍(정면 x-z)이 있는 판 → 상자들로 나눔"""
    x0, x1, y0, y1, z0, z1 = b
    if not holes:
        return [b]
    _, hx, hz, hw, hh = holes[0]
    hx0, hx1, hz0, hz1 = max(hx - hw / 2, x0), min(hx + hw / 2, x1), max(hz - hh / 2, z0), min(hz + hh / 2, z1)
    if hx0 >= hx1 or hz0 >= hz1:
        return [b]
    out = [(x0, x1, y0, y1, z0, hz0), (x0, x1, y0, y1, hz1, z1),
           (x0, hx0, y0, y1, hz0, hz1), (hx1, x1, y0, y1, hz0, hz1)]
    return [o for o in out if o[1] - o[0] > 1e-6 and o[5] - o[4] > 1e-6]


def finger_boxes(q, p, d):
    """사개 판: 천판·지판(x 끝에 손), 옆판(z 끝에 손)"""
    x0, x1, y0, y1, z0, z1 = q["b"]
    t = p["t"]
    bn = core.pins(p["D"], p["pin_pitch"])
    segs = list(zip(bn[:-1], bn[1:]))
    out = []
    if q["name"] in ("천판", "지판"):
        out.append((x0 + t, x1 - t, y0, y1, z0, z1))
        for i, (a, b) in enumerate(segs):
            if i % 2 == 0:
                out += [(x0, x0 + t, a, b, z0, z1), (x1 - t, x1, a, b, z0, z1)]
    else:   # 옆판: 위·아래 끝 t 구간은 홀수 구간만
        f = p["foot_h"]
        out.append((x0, x1, y0, y1, f + t, p["H"] - t))
        for i, (a, b) in enumerate(segs):
            if i % 2 == 1:
                out += [(x0, x1, a, b, f, f + t), (x0, x1, a, b, p["H"] - t, p["H"])]
    return out


def shelf_boxes(q):
    x0, x1, y0, y1, z0, z1 = q["b"]
    sl = q.get("slots", [])
    if not sl:
        return [q["b"]]
    sy0, sy1 = sl[0][1], sl[0][1] + sl[0][3]
    out = [(x0, x1, y0, sy0, z0, z1), (x0, x1, sy1, y1, z0, z1)]
    xs = x0
    for sx, _, sw, _ in sl:
        out.append((xs, sx, sy0, sy1, z0, z1))
        xs = sx + sw
    out.append((xs, x1, sy0, sy1, z0, z1))
    return [o for o in out if o[1] - o[0] > 1e-6]


GROUP = {   # 뷰어 레이어
    "shell": "겉판", "foot": "겉판", "frame": "겉판", "door": "문", "ins": "단열재", "lining": "속판",
    "film": "열원", "ptc": "열원", "rack": "거치대", "shelf": "선반", "cleat": "선반",
    "gasket": "가스켓·철물", "mag": "가스켓·철물", "ctl": "조절기", "handle": "문",
}


def part_mesh(q, p, d):
    x0, x1, y0, y1, z0, z1 = q["b"]
    if q["name"] in ("천판", "지판", "옆판(좌)", "옆판(우)"):
        return merge([box_mesh(*b) for b in finger_boxes(q, p, d)])
    if "shelf" in q["tags"]:
        return merge([box_mesh(*b) for b in shelf_boxes(q)])
    if "prof" in q:
        return extrude(q["prof"], "x", x0, x1)
    if q.get("shape") in ("cyl", "disc"):
        r = (x1 - x0) / 2
        return extrude(circle((x0 + x1) / 2, (z0 + z1) / 2, r), "y", y0, y1)
    if q.get("round_top"):
        return extrude(core._round_rect(x0, z0, x1 - x0, z1 - z0, p["rack_r"]), "y", y0, y1)
    if q.get("holes3d"):
        return merge([box_mesh(*b) for b in box_with_holes(q["b"], q["holes3d"])])
    return box_mesh(x0, x1, y0, y1, z0, z1)


def model(params=None):
    """[(이름, 재료, 레이어, 문쪽, V, F)] + 활 곡선"""
    core.apply(params)
    parts, d = core.build()
    p = core.P()
    out = []
    for q in parts:
        V, F = part_mesh(q, p, d)
        if len(F) == 0:
            continue
        layer = next((GROUP[t] for t in ("handle", "door", "ctl", "mag", "gasket", "film", "ptc", "rack", "shelf",
                                          "cleat", "ins", "lining", "frame", "foot", "shell") if t in q["tags"]), "겉판")
        door = "L" if "doorL" in q["tags"] else ("R" if "doorR" in q["tags"] else "")
        out.append(dict(name=q["name"], mat=q["mat"], layer=layer, door=door, V=V, F=F))
    bows = {}
    for st in ("open", "closed"):
        (xo, zo), (xi, zi), _ = core.bow_curves(d, st)
        xc, zc = (xo + xi) / 2, (zo + zi) / 2
        ys = [d["cy1"] - p["rack_back"] - p["bow_pitch"] * (k + 0.5) for k in range(int(p["n_bows"]))]
        bows[st] = dict(x=[round(float(v), 1) for v in xc[::3]], z=[round(float(v), 1) for v in zc[::3]], y=ys)
    return out, d, bows


# ---------------------------------------------------------------- 내보내기
def _hex(c):
    return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))


def write_obj(path, meshes):
    base = os.path.splitext(path)[0]
    mtl = base + ".mtl"
    with open(mtl, "w", encoding="utf-8") as fp:
        for k, (nm, col) in core.MAT.items():
            r, g, b = _hex(col)
            fp.write(f"newmtl {k}\nKd {r:.3f} {g:.3f} {b:.3f}\nKa 0 0 0\nd 1\n\n")
    n = 1
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(f"# 각궁 점화장 3D 모델 (단위 mm, Z 위)\nmtllib {os.path.basename(mtl)}\n")
        for i, m in enumerate(meshes):
            fp.write(f"o {i:02d}_{m['name'].replace(' ', '_')}\nusemtl {m['mat']}\n")
            for v in m["V"]:
                fp.write(f"v {v[0]:.2f} {v[1]:.2f} {v[2]:.2f}\n")
            for f in m["F"]:
                fp.write(f"f {f[0] + n} {f[1] + n} {f[2] + n}\n")
            n += len(m["V"])
    return [path, mtl]


def write_dae(path, meshes):
    """Collada 1.4 — SketchUp: 파일 → 가져오기 → *.dae"""
    from xml.sax.saxutils import escape
    mats = sorted({m["mat"] for m in meshes})
    o = ['<?xml version="1.0" encoding="utf-8"?>',
         '<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">',
         '<asset><unit name="millimeter" meter="0.001"/><up_axis>Z_UP</up_axis></asset>',
         '<library_effects>']
    for k in mats:
        r, g, b = _hex(core.MAT[k][1])
        o.append(f'<effect id="fx_{k}"><profile_COMMON><technique sid="c"><lambert><diffuse>'
                 f'<color>{r:.3f} {g:.3f} {b:.3f} 1</color></diffuse></lambert></technique></profile_COMMON></effect>')
    o.append('</library_effects><library_materials>')
    for k in mats:
        o.append(f'<material id="m_{k}" name="{escape(core.MAT[k][0])}"><instance_effect url="#fx_{k}"/></material>')
    o.append('</library_materials><library_geometries>')
    for i, m in enumerate(meshes):
        V, F = m["V"], m["F"]
        pos = " ".join(f"{v:.2f}" for v in V.ravel())
        idx = " ".join(str(int(v)) for v in F.ravel())
        o.append(f'<geometry id="g{i}"><mesh><source id="g{i}p"><float_array id="g{i}pa" count="{V.size}">{pos}</float_array>'
                 f'<technique_common><accessor source="#g{i}pa" count="{len(V)}" stride="3"><param name="X" type="float"/>'
                 f'<param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>'
                 f'<vertices id="g{i}v"><input semantic="POSITION" source="#g{i}p"/></vertices>'
                 f'<triangles material="mat" count="{len(F)}"><input semantic="VERTEX" source="#g{i}v" offset="0"/><p>{idx}</p></triangles>'
                 f'</mesh></geometry>')
    o.append('</library_geometries><library_visual_scenes><visual_scene id="scene">')
    for i, m in enumerate(meshes):
        o.append(f'<node id="n{i}" name="{escape(f"{i:02d} {m["name"]}")}"><instance_geometry url="#g{i}"><bind_material><technique_common>'
                 f'<instance_material symbol="mat" target="#m_{m["mat"]}"/></technique_common></bind_material></instance_geometry></node>')
    o.append('</visual_scene></library_visual_scenes><scene><instance_visual_scene url="#scene"/></scene></COLLADA>')
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(o))
    return [path]


def _vendor(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(base, "assets", "vendor", name), encoding="utf-8") as fp:
        return fp.read()


def write_viewer(path, meshes, d, bows):
    p = core.P()
    data = []
    for m in meshes:
        data.append(dict(n=m["name"], c=core.MAT[m["mat"]][1], l=m["layer"], d=m["door"],
                         v=base64.b64encode(m["V"].astype("<f4").tobytes()).decode(),
                         f=base64.b64encode(m["F"].astype("<u4").tobytes()).decode(),
                         o=0.55 if m["mat"] in ("ins",) else 1.0))
    info = dict(W=p["W"], H=p["H"], D=p["D"], t=p["t"], gap=p["gap"], n=int(p["n_bows"]),
                limb=p["bow_limb"], cw=round(d["cw"]), ch=round(d["ch"]), cd=round(d["cd"]),
                door=p["door_h"], lower=p["lower_h"])
    html = (VIEWER.replace("__THREE__", _vendor("three.min.js"))
            .replace("__ORBIT__", _vendor("OrbitControls.js"))
            .replace("__DATA__", json.dumps(data))
            .replace("__BOWS__", json.dumps(bows))
            .replace("__INFO__", json.dumps(info)))
    with open(path, "w", encoding="utf-8") as fp:
        fp.write(html)
    return [path]


def export_3d(outdir="output", params=None):
    meshes, d, bows = model(params)
    p = core.P()
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, f"jeomhwajang_W{p['W']:.0f}_H{p['H']:.0f}_D{p['D']:.0f}_bow{int(p['n_bows'])}")
    files = []
    files += write_obj(base + "_3d.obj", meshes)
    files += write_dae(base + "_3d_sketchup.dae", meshes)
    files += write_viewer(base + "_3d_viewer.html", meshes, d, bows)
    return files


VIEWER = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>각궁 점화장 3D 뷰어</title>
<style>
 *{box-sizing:border-box} html,body{margin:0;height:100%;background:#f4f1ea;color:#2b2620;
   font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif;overflow:hidden}
 #v{position:fixed;inset:0}
 #ui{position:fixed;top:12px;left:12px;width:250px;background:#fffdf8ee;border:1px solid #d8d0c2;border-radius:10px;
   padding:12px 14px;font-size:13px;box-shadow:0 2px 10px #0001;max-height:calc(100% - 24px);overflow:auto}
 h1{font-size:15px;margin:0 0 4px} .mut{color:#7a7166;font-size:12px;margin-bottom:8px}
 h2{font-size:12px;margin:12px 0 4px;color:#7a7166;font-weight:600}
 label{display:flex;align-items:center;gap:6px;margin:3px 0;cursor:pointer}
 input[type=range]{width:100%} .row{display:flex;justify-content:space-between}
 button{margin-top:8px;width:100%;padding:6px;border:1px solid #c9bfae;background:#fff;border-radius:6px;cursor:pointer}
 #sw{display:inline-block;width:10px;height:10px;border-radius:2px}
</style></head><body>
<div id="v"></div>
<div id="ui">
 <h1>각궁 점화장 3D</h1>
 <div class="mut" id="dims"></div>
 <h2>문 열기</h2>
 <input type="range" id="door" min="0" max="110" value="0"><div class="row mut"><span>닫힘</span><span id="dv">0°</span><span>110°</span></div>
 <h2>단면 보기 (왼쪽부터 자르기)</h2>
 <label><input type="checkbox" id="cut"> 단면 켜기</label>
 <input type="range" id="cx" min="0" max="1000" value="500">
 <h2>보이기</h2>
 <div id="layers"></div>
 <h2>부린활</h2>
 <label><input type="radio" name="bow" value="none"> 숨김</label>
 <label><input type="radio" name="bow" value="open" checked> 벌어진 활</label>
 <label><input type="radio" name="bow" value="closed"> 오므라든 활</label>
 <button id="reset">시점 처음으로</button>
 <div class="mut" style="margin-top:8px">왼쪽 끌기: 회전 · 오른쪽 끌기: 이동 · 휠: 확대</div>
</div>
<script>__THREE__</script>
<script>__ORBIT__</script>
<script>
const DATA=__DATA__, BOWS=__BOWS__, INFO=__INFO__;
const el=document.getElementById('v');
const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(window.devicePixelRatio); renderer.localClippingEnabled=true;
renderer.setClearColor(0xf4f1ea); el.appendChild(renderer.domElement);
const scene=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(35,1,10,20000); cam.up.set(0,0,1);
const ctl=new THREE.OrbitControls(cam,renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x8a7a66,0.8));
const sun=new THREE.DirectionalLight(0xffffff,0.55); sun.position.set(-1200,-2000,2500); sun.intensity=0.6; scene.add(sun);
const sun2=new THREE.DirectionalLight(0xffffff,0.25); sun2.position.set(1500,1500,800); scene.add(sun2);
const clip=new THREE.Plane(new THREE.Vector3(1,0,0),0); const clips=[];
function dec(b64,T){const s=atob(b64),u=new Uint8Array(s.length);for(let i=0;i<s.length;i++)u[i]=s.charCodeAt(i);return new T(u.buffer);}
const pivL=new THREE.Group(), pivR=new THREE.Group(), body=new THREE.Group();
const xL=INFO.t+INFO.gap, xR=INFO.W-INFO.t-INFO.gap;
pivL.position.set(xL,0,0); pivR.position.set(xR,0,0); scene.add(pivL,pivR,body);
const layers={};
for(const m of DATA){
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(dec(m.v,Float32Array),3));
  g.setIndex(new THREE.BufferAttribute(dec(m.f,Uint32Array),1)); g.computeVertexNormals();
  const mat=new THREE.MeshLambertMaterial({color:m.c,transparent:m.o<1,opacity:m.o,clippingPlanes:clips,clipShadows:true,side:THREE.DoubleSide,flatShading:true});
  const mesh=new THREE.Mesh(g,mat);
  const edges=new THREE.LineSegments(new THREE.EdgesGeometry(g,20),new THREE.LineBasicMaterial({color:0x5a4a35,transparent:true,opacity:0.35,clippingPlanes:clips}));
  const grp=new THREE.Group(); grp.add(mesh,edges);
  if(m.d==='L'){grp.position.x=-xL;pivL.add(grp);} else if(m.d==='R'){grp.position.x=-xR;pivR.add(grp);} else body.add(grp);
  (layers[m.l]=layers[m.l]||[]).push(grp);
}
// 부린활
const bowGrp={};
for(const st of ['open','closed']){
  const G=new THREE.Group(), B=BOWS[st];
  for(const y of B.y){
    const pts=B.x.map((x,i)=>new THREE.Vector3(x,y,B.z[i]));
    const tube=new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts),200,INFO.limb/2,8,false);
    G.add(new THREE.Mesh(tube,new THREE.MeshLambertMaterial({color:st==='open'?0x9a6b2f:0x7a5326,clippingPlanes:clips})));
  }
  bowGrp[st]=G; scene.add(G);
}
bowGrp.closed.visible=false;
document.querySelectorAll('input[name=bow]').forEach(r=>r.onchange=()=>{
  const v=document.querySelector('input[name=bow]:checked').value; for(const k in bowGrp)bowGrp[k].visible=(k===v);});
const order=['겉판','문','단열재','속판','열원','선반','거치대','조절기','가스켓·철물'];
const L=document.getElementById('layers');
for(const k of order){ if(!layers[k])continue;
  const lb=document.createElement('label'); const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=true;
  cb.onchange=()=>layers[k].forEach(o=>o.visible=cb.checked); lb.append(cb,document.createTextNode(k)); L.append(lb);}
document.getElementById('dims').textContent=`외형 ${INFO.W}×${INFO.H}×${INFO.D} · 활 칸 ${INFO.cw}×${INFO.ch}×${INFO.cd} · 문 ${INFO.door} · 하부 ${INFO.lower} · 부린활 ${INFO.n}장`;
const door=document.getElementById('door'), dv=document.getElementById('dv');
door.oninput=()=>{const a=door.value*Math.PI/180; pivL.rotation.z=-a; pivR.rotation.z=a; dv.textContent=door.value+'°';};
const cut=document.getElementById('cut'), cx=document.getElementById('cx');
function setCut(){clips.length=0; if(cut.checked){clip.constant=-(cx.value/1000*INFO.W); clips.push(clip);}
  scene.traverse(o=>{if(o.material)o.material.needsUpdate=true;});}
cut.onchange=setCut; cx.oninput=setCut;
function home(){const c=new THREE.Vector3(INFO.W/2,INFO.D/2,INFO.H/2); ctl.target.copy(c);
  cam.position.set(INFO.W*0.15-INFO.W*0.9,-INFO.D*6,INFO.H*1.3); ctl.update();}
document.getElementById('reset').onclick=home;
function size(){const w=el.clientWidth,h=el.clientHeight; renderer.setSize(w,h); cam.aspect=w/h; cam.updateProjectionMatrix();}
window.addEventListener('resize',size); size(); home();
(function loop(){requestAnimationFrame(loop); renderer.render(scene,cam);})();
</script></body></html>
"""

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for f_ in export_3d("output"):
        print(f_)
