"""아이콘: 문 열린 점화장 안에 걸린 부린활"""
from PIL import Image, ImageDraw
import os

def draw(sz):
    s = sz / 256
    im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = lambda *v: [x * s for x in v]
    d.rounded_rectangle(S(28, 30, 228, 236), radius=14 * s, fill=(140, 52, 40), outline=(70, 30, 20), width=max(1, int(6 * s)))
    d.rectangle(S(46, 48, 210, 190), fill=(250, 214, 150))
    d.rectangle(S(46, 196, 210, 222), fill=(170, 70, 50))
    d.arc(S(66, 66, 190, 186), start=118, end=422, fill=(120, 70, 25), width=max(2, int(10 * s)))
    d.rectangle(S(118, 60, 138, 80), fill=(60, 40, 30))
    d.ellipse(S(114, 168, 142, 186), fill=(235, 90, 40))
    return im

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(base, exist_ok=True)
big = draw(256)
big.save(os.path.join(base, "icon.png"))
big.save(os.path.join(base, "icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok")
