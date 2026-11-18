import os, re, sys, glob, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from draw import *
from PIL import ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SERIF = os.path.join(ROOT, "tools", "fonts", "EBGaramond-Regular.ttf"); SERIF_SB = os.path.join(ROOT, "tools", "fonts", "EBGaramond-SemiBold.ttf")
T = {  # first name -> traits
 "Kael":"short","Oren":"silver beard","Halia":"bun old","Tobin":"hat","Edran":"short slate","Pira":"long","Evara":"long old","Ommeth":"wild beard old",
 "Quilla":"bun collar","Lethan":"neat collar","Gast":"broad mustache","Sael":"ponytail","Rhaen":"short collar","Thessa":"long","Varek":"swept",
 "Kethran":"crop collar","Nareth":"beard broad","Bruk":"bald broad","Jaro":"messy","Zia":"long straight","Marit":"curly","Corra":"braid","Orla":"bob glasses",
 "Okun":"giant child","Hesk":"tribe","Unna":"tribe long","Teyo":"tribe child","Velira":"long","Ruvan":"white","Voren":"short","Gorun":"giant broad",
 "Hollis":"grey","Wren":"rope","Iris":"old bun","Mara":"long","Asha":"curly","Elias":"tall","Theo":"messy","Jonah":"hardhat","Wade":"crop broad",
 "Dana":"bob","Davan":"cap","Ilo":"small","Hannah":"ponytail","Nyra":"long","Tavo":"short","Harn":"giant","Sura":"braid","Damar":"crown","Aren":"short",
 "Tavren":"short","Yanna":"bun","Dunmar":"short","Teren":"collar","Ilsa":"long","Ixen":"messy","Lio":"short","Saba":"long","Quen":"collar","Sefa":"bob glasses",
 "Talen":"ponytail","Imra":"short","Liora":"braid","Tolas":"beard",
}
def tint(name):
    h = int(hashlib.md5(name.encode()).hexdigest()[:6], 16)
    return [(70,110,200),(200,140,80),(120,90,180),(90,160,140),(190,90,110),(160,160,90)][h % 6]

def bust(d, cx, base, s, tr, col):
    giant = "giant" in tr or "broad" in tr; child = "child" in tr; small = "small" in tr; tall = "tall" in tr
    sw = s*(0.62 if giant else 0.42 if child else 0.46 if small else 0.5)
    hr = s*(0.17 if child else 0.15 if small else 0.16)
    hy = base - s*(0.62 if child else 0.72 if tall else 0.68)
    if "grey" in tr:
        d.ellipse([cx-hr*0.9, hy-hr*1.6, cx+hr*0.9, hy+hr], fill=col)
        d.ellipse([cx-hr*0.55, hy-hr*0.5, cx-hr*0.1, hy+hr*0.1], fill=(0,0,0)); d.ellipse([cx+hr*0.1, hy-hr*0.5, cx+hr*0.55, hy+hr*0.1], fill=(0,0,0))
    else:
        d.ellipse([cx-hr, hy-hr, cx+hr, hy+hr], fill=col)
    d.rectangle([cx-hr*0.4, hy+hr*0.6, cx+hr*0.4, hy+hr*1.4], fill=col)
    d.pieslice([cx-sw, hy+hr*1.1, cx+sw, base+sw*0.9], 180, 360, fill=col); d.rectangle([cx-sw, base-2, cx+sw, base], fill=col)
    if "long" in tr or "braid" in tr: d.polygon([(cx-hr*1.05, hy), (cx+hr*1.05, hy), (cx+hr*1.15, hy+hr*2.4), (cx-hr*1.15, hy+hr*2.4)], fill=col)
    if "bun" in tr: d.ellipse([cx-hr*0.5, hy-hr*1.55, cx+hr*0.5, hy-hr*0.65], fill=col)
    if "ponytail" in tr: d.polygon([(cx+hr*0.6, hy-hr*0.4), (cx+hr*1.5, hy+hr*0.5), (cx+hr*1.2, hy+hr*1.4), (cx+hr*0.8, hy)], fill=col)
    if "wild" in tr or "messy" in tr:
        for a in range(-80, 81, 20): d.line([(cx, hy-hr*0.2), (cx+math.sin(math.radians(a))*hr*1.4, hy-math.cos(math.radians(a))*hr*1.4)], fill=col, width=int(hr*0.25))
    if "beard" in tr: d.polygon([(cx-hr*0.8, hy+hr*0.2), (cx+hr*0.8, hy+hr*0.2), (cx, hy+hr*1.6)], fill=col)
    if "mustache" in tr: d.rectangle([cx-hr*0.7, hy+hr*0.35, cx+hr*0.7, hy+hr*0.6], fill=col)
    if "hat" in tr: d.rectangle([cx-hr*1.5, hy-hr*0.7, cx+hr*1.5, hy-hr*0.5], fill=col); d.rectangle([cx-hr*0.9, hy-hr*1.4, cx+hr*0.9, hy-hr*0.6], fill=col)
    if "hardhat" in tr: d.pieslice([cx-hr*1.15, hy-hr*1.25, cx+hr*1.15, hy+hr*0.4], 180, 360, fill=(220,170,40))
    if "cap" in tr: d.pieslice([cx-hr*1.05, hy-hr*1.2, cx+hr*1.05, hy+hr*0.3], 180, 360, fill=col); d.rectangle([cx-hr*0.2, hy-hr*0.5, cx+hr*1.5, hy-hr*0.35], fill=col)
    if "crown" in tr: d.polygon([(cx-hr, hy-hr*0.7), (cx-hr*0.6, hy-hr*1.4), (cx-hr*0.2, hy-hr*0.9), (cx+hr*0.2, hy-hr*1.5), (cx+hr*0.6, hy-hr*0.9), (cx+hr, hy-hr*1.4), (cx+hr, hy-hr*0.7)], fill=(210,170,70))
    if "collar" in tr: d.polygon([(cx-hr*1.2, hy+hr*1.2), (cx, hy+hr*2.2), (cx+hr*1.2, hy+hr*1.2), (cx+hr*1.4, hy+hr*1.0), (cx, hy+hr*1.8), (cx-hr*1.4, hy+hr*1.0)], fill=(40,40,50))
    if "glasses" in tr:
        for dx in (-0.45, 0.45): d.ellipse([cx+dx*hr-hr*0.33, hy-hr*0.2, cx+dx*hr+hr*0.33, hy+hr*0.3], outline=(220,220,230), width=5)
    if "rope" in tr: d.arc([cx-sw*0.6, base-sw*0.5, cx+sw*0.6, base+sw*0.3], 200, 340, fill=(200,170,110), width=10)
    if "slate" in tr: d.rectangle([cx+sw*0.35, base-s*0.25, cx+sw*0.75, base-s*0.02], fill=(90,90,100))
    if "tribe" in tr: d.line([(cx-hr*0.6, hy+hr*0.1), (cx+hr*0.6, hy+hr*0.1)], fill=(170,60,40), width=8)
    return hy, hr

def tile(name, tr, older=False, gold=False):
    w, h = 560, 600; im = Image.new("RGB", (w, h), (10,12,20)); c = tint(name)
    im = im.resize((w, h)); g = Image.new("RGB", (w, h), (0,0,0)); dg = ImageDraw.Draw(g)
    for i in range(10, 0, -1): dg.ellipse([w/2-220*i/10, 250-220*i/10, w/2+220*i/10, 250+220*i/10], fill=tuple(int(v*0.55*(1-i/11)) for v in c))
    g = g.filter(ImageFilter.GaussianBlur(30)); im = Image.blend(im, g, 0.9)
    d = ImageDraw.Draw(im); col = (205,170,80) if gold else (6,8,14)
    if older and "child" in tr: tr = tr.replace("child", "")       # mortals grow up
    hy, hr = bust(d, w/2, 470, 330, tr, col)
    if older:  # silvered hair-light: the ages passing
        d.arc([w/2-hr*1.08, hy-hr*1.08, w/2+hr*1.08, hy+hr*1.08], 200, 340, fill=(205,210,220), width=7)
    d.rectangle([0, 500, w, h], fill=(10,12,20))
    f = ImageFont.truetype(SERIF_SB, 46); f2 = ImageFont.truetype(SERIF, 30)
    d.text(((w-d.textlength(name, font=f))/2, 505), name, font=f, fill=(236,228,208))
    if older: d.text(((w-d.textlength("ages later", font=f2))/2, 558), "ages later", font=f2, fill=(160,160,175))
    return im

def cast_names(book):
    t = open(os.path.join(ROOT, f"Rough Draft 8 Book {book}", "000c - Cast.md"), encoding="utf-8").read()
    out = []
    for line in t.split("\n"):
        if not line.startswith("**") or "**:" not in line and not re.search(r"\*\*[^*]+\*\* and \*\*", line): continue
        for n in re.findall(r"\*\*([^*]+)\*\*", line.split(":")[0]):
            if n.strip() and not n.lower().startswith(("on ", "the ")): out.append(n.strip())
    seen = []; [seen.append(n) for n in out if n not in seen]; return seen

def grid_pages(book):
    names = cast_names(book); b1 = set(n.split()[0] for n in cast_names(1)) if book != 1 else set()
    tiles = []
    for n in names:
        first = n.split()[0]; tr = T.get(first, "short")
        older = book == 2 and first in b1
        tiles.append(tile(n, tr, older=older))
    if book == 3: tiles.append(tile("The other Kael", "short collar", gold=True))
    pages, per = [], 12
    for p in range(0, len(tiles), per):
        page = canvas((8,10,18), (20,22,34)); d = ImageDraw.Draw(page)
        f = ImageFont.truetype(SERIF_SB, 70); title = "The People of the Story"
        d.text(((W-d.textlength(title, font=f))/2, 90), title, font=f, fill=(236,228,208))
        for i, t in enumerate(tiles[p:p+per]):
            page.paste(t, (30 + (i % 3) * 590, 230 + (i // 3) * 615))
        pages.append(page)
    outdir = lambda b: os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "books", f"book {b}", "images", "cast")   # straight into the book's images
    os.makedirs(outdir(book), exist_ok=True)
    paths = []
    for i, pg in enumerate(pages):
        path = os.path.join(outdir(book), f"cast-b{book}-{i+1}.jpg"); pg.save(path, quality=88); paths.append(path)
    return names, paths

if __name__ == "__main__":
    for b in (1, 2, 3):
        names, paths = grid_pages(b); print(b, len(names), "characters,", len(paths), "pages")
