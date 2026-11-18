from draw import *
S = []   # (book, file_prefix, anchor_or_None, id, caption, fn)
def sc(book, pre, anchor, cap):
    def wrap(fn): S.append((book, pre, anchor, f"b{book}-{pre.strip()}-{len([s for s in S if s[0]==book and s[1]==pre])+1}", cap, fn)); return fn
    return wrap

# ---------------- BOOK ONE ----------------
@sc(1,"00",None,"The singing came first, and it moved down level by level.")
def _(im):
    stars(im, 300, 11, 0.5); im=glow(im, W*0.5, H*0.62, 520, (255,200,140), 0.8)
    dome_city(im, int(H*0.78), 11, lights=3); return lights_rising(im, 120, 11, 0.75, 0.2)
@sc(1,"01",None,"When you reach the top of a mountain, in the distance you see the next mountain. The journey never ends, it just passes to the next generation to finish.")
def _(im):
    stars(im, 500, 1); im=glow(im, W*0.62, H*0.28, 160)
    mountains(im, H*0.62, 380, 1, (48,52,80)); mountains(im, H*0.72, 260, 2, (28,30,48))
    peak(im, W*0.48, H, 1500, 900); person(im, W*0.45, H-900+8, 120); person(im, W*0.5, H-900+8, 85); return im
@sc(1,"02","door that hadn't quite shut","A door that hadn't quite shut.")
def _(im):
    im=canvas((10,10,14),(24,22,28)); d=ImageDraw.Draw(im)
    d.rectangle([W*0.32, H*0.18, W*0.68, H*0.82], fill=(8,8,10)); d.polygon([(W*0.62,H*0.18),(W*0.68,H*0.18),(W*0.68,H*0.82),(W*0.62,H*0.82)], fill=(230,200,140))
    im=glow(im, W*0.66, H*0.5, 260, (255,200,120), 0.7); person(im, W*0.42, H*0.82, 360, "sit"); return im
@sc(1,"03","Appreciate the view","Come back sometimes. Appreciate the view.")
def _(im):
    im=canvas((40,52,96),(232,170,120)); im=glow(im, W*0.5, H*0.55, 300, (255,220,160), 0.9)
    mountains(im, H*0.6, 300, 3, (60,58,90)); ground(im, H*0.74); d=ImageDraw.Draw(im); d.rectangle([W*0.2,H*0.72,W*0.8,H*0.74], fill=INK)
    person(im, W*0.42, H*0.74, 330, "sit"); person(im, W*0.58, H*0.74, 330, "sit", facing=-1); return im
@sc(1,"04","I found Pira","Keep it safe. All of it. Even the parts that don't fit.")
def _(im):
    im=canvas((16,14,18),(40,32,30)); d=ImageDraw.Draw(im)
    for k in range(7): d.rectangle([60+k*250, H*0.1, 260+k*250, H*0.85], fill=(22,18,18)); [d.rectangle([70+k*250, H*0.12+j*120, 250+k*250, H*0.12+j*120+90], fill=(60,40,30)) for j in range(13)]
    im=glow(im, W*0.5, H*0.55, 300, (255,190,110), 0.7); person(im, W*0.5, H*0.86, 600, "stand"); return im
@sc(1,"05","Edran","A line on the map that hadn't been there in four thousand years.")
def _(im):
    stars(im, 900, 5, 1.0); d=ImageDraw.Draw(im); r=random.Random(5); pts=[(W*0.1+i*W*0.08, H*0.75-i*H*0.06+r.randrange(-60,60)) for i in range(11)]
    for a,b in zip(pts,pts[1:]): d.line([a,b], fill=(240,210,150), width=5)
    for p in pts: im=glow(im, p[0], p[1], 40, (255,220,160), 0.9)
    return im
@sc(1,"06","said Thessa Orin","The edge of charted space.")
def _(im):
    stars(im, 600, 6); im=glow(im, W*0.3, H*0.45, 520, (210,150,90), 0.5); disc(im, W*0.3, H*0.45, 430, (150,100,70))
    return ship(im, W*0.66, H*0.62, 520)
@sc(1,"07","*What comes after?*","What comes after?")
def _(im):
    im=canvas((14,12,20),(40,34,40)); d=ImageDraw.Draw(im)
    for i in range(8): d.rectangle([0, H*0.3+i*150, W, H*0.3+i*150+30], fill=(30,26,34))
    crowd(im, 80, W-80, H*0.72, 150, 60, 7); im=glow(im, W*0.5, H*0.83, 260, (255,210,150), 0.6); person(im, W*0.5, H*0.9, 420); return im
@sc(1,"07b",None,"Somebody had to remember.")
def _(im):
    im=canvas((40,40,70),(180,120,100)); dome_city(im, int(H*0.6), 8); ground(im, H*0.75); d=ImageDraw.Draw(im)
    d.rectangle([W*0.15, H*0.7, W*0.85, H*0.75], fill=(20,18,24)); person(im, W*0.5, H*0.7, 300, "sit"); return im
@sc(1,"08","Council security","I'm very good at counting people when they leave.")
def _(im):
    im=canvas((8,8,12),(18,18,24)); d=ImageDraw.Draw(im); d.rectangle([W*0.3, H*0.15, W*0.7, H*0.9], fill=(200,180,140))
    im=glow(im, W*0.5, H*0.5, 500, (255,210,150), 0.5); person(im, W*0.5, H*0.9, 1150, "coat"); return im
@sc(1,"09","Somehow, against all reason, they had become friends.","The crew of the Farlight.")
def _(im):
    stars(im, 400, 9); d=ImageDraw.Draw(im); d.rectangle([0,H*0.2,W,H*0.24], fill=(30,34,48)); d.rectangle([W*0.1,H*0.2,W*0.13,H],fill=(30,34,48)); d.rectangle([W*0.87,H*0.2,W*0.9,H],fill=(30,34,48))
    im=ship(im, W*0.5, H*0.42, 1100); ground(im, H*0.8); [person(im, W*0.14+i*W*0.072, H*0.8, 230) for i in range(11)]; return im
@sc(1,"10","Sael flew her out herself","The great frames of the orbital docks slid past.")
def _(im):
    stars(im, 700, 10); im=planet(im, W*0.5, H*1.05, 900); d=ImageDraw.Draw(im)
    for i in range(6): d.rectangle([W*0.05+i*300, H*0.25, W*0.05+i*300+40, H*0.6], fill=(30,34,48))
    return ship(im, W*0.55, H*0.42, 700)
@sc(1,"11","Whoever ate my fruit","Whoever ate my fruit, I know it was you.")
def _(im):
    im=canvas((12,14,18),(30,32,36)); d=ImageDraw.Draw(im); d.rectangle([W*0.15,H*0.15,W*0.85,H*0.65], fill=(60,58,50))
    r=random.Random(11)
    for i in range(14):
        x,y=r.randrange(int(W*0.18),int(W*0.72)), r.randrange(int(H*0.18),int(H*0.55)); d.rectangle([x,y,x+180,y+130], fill=(220,205,160)); [d.line([(x+15,y+25+k*22),(x+160,y+25+k*22)], fill=(120,100,80), width=3) for k in range(4)]
    im=glow(im, W*0.5, H*0.4, 400, (255,220,170), 0.4); person(im, W*0.5, H*0.95, 700); return im
@sc(1,"12","It took four hours, and Kael felt every one of them.","The first hour was the stars.")
def _(im):
    stars(im, 500, 12, 1.0); im=well_merge(im); return ship(im, W*0.5, H*0.6, 480)
@sc(1,"13",None,"The city that died together.")
def _(im):
    im=canvas((60,40,30),(190,140,90)); im=glow(im, W*0.5, H*0.38, 300, (255,230,190), 0.7); dome_city(im, int(H*0.8), 13, col=(30,22,20)); return im
@sc(1,"14",None,"Four hundred and twelve jars.")
def _(im):
    im=canvas((10,10,14),(26,24,26)); d=ImageDraw.Draw(im)
    for row in range(6):
        for i in range(10): x=120+i*160; y=H*0.25+row*260; d.rounded_rectangle([x,y,x+110,y+200], radius=30, fill=(80,90,100), outline=(150,160,170))
    return glow(im, W*0.5, H*0.55, 600, (180,200,230), 0.3)
@sc(1,"14b",None,"Varek kept one.")
def _(im):
    im=canvas((6,6,10),(16,14,20)); im=glow(im, W*0.5, H*0.55, 260, (200,200,180), 0.9); d=ImageDraw.Draw(im)
    d.rounded_rectangle([W*0.42, H*0.5, W*0.58, H*0.6], radius=40, fill=(120,120,115)); person(im, W*0.5, H*1.0, 1300, "coat"); return im
@sc(1,"15",None,"Kethran dug with his bare hands.")
def _(im):
    im=canvas((10,8,8),(30,24,20)); d=ImageDraw.Draw(im); r=random.Random(15)
    for _ in range(40): x,y=r.randrange(W),r.randrange(int(H*0.3),H); s=r.randrange(60,220); d.polygon([(x,y),(x+s,y-s*0.4),(x+s*1.2,y+s*0.3),(x+s*0.2,y+s*0.5)], fill=(40,34,30))
    im=glow(im, W*0.4, H*0.6, 220, (255,200,120), 0.8); person(im, W*0.45, H*0.82, 400, "kneel"); person(im, W*0.62, H*0.82, 380, "kneel", facing=-1); return im
@sc(1,"16",None,"Seven people who had come for seven reasons.")
def _(im):
    stars(im, 700, 16); ground(im, H*0.78); im=glow(im, W*0.5, H*0.76, 160, (255,170,90), 1.0)
    for i,a in enumerate([200,260,320,20,80,140,170]): person(im, W*0.5+math.cos(math.radians(a))*360, H*0.78+math.sin(math.radians(a))*40, 230, "sit")
    return im
@sc(1,"17","Ommeth","The rambling old man on the wall.")
def _(im):
    im=canvas((30,32,60),(150,110,110)); dome_city(im, int(H*0.55), 17); ground(im, H*0.74); d=ImageDraw.Draw(im); d.rectangle([0,H*0.69,W,H*0.74], fill=(16,14,20))
    person(im, W*0.38, H*0.69, 320, "sit"); person(im, W*0.62, H*0.69, 340, "sit", facing=-1); return im
@sc(1,"18","The Veil's magnetic","You could hide a moon in there.")
def _(im):
    stars(im, 600, 18); im=glow(im, W*0.5, H*0.45, 800, (120,90,170), 0.6); im=glow(im, W*0.55, H*0.5, 600, (200,140,200), 0.4)
    moon(im, W*0.52, H*0.48, 170); return im
@sc(1,"19","Year 9.","The moon came in on the display, a dark scarred lump of rock and iron.")
def _(im):
    stars(im, 700, 19); im=glow(im, W*0.6, H*0.4, 900, (120,90,170), 0.55); moon(im, W*0.35, H*0.55, 300, 19, (150,150,160)); return im
@sc(1,"19b","The second time, nobody laughed.","Bin forty.")
def _(im):
    im=canvas((10,12,16),(26,28,34)); d=ImageDraw.Draw(im)
    for i in range(5): d.rectangle([80+i*340, H*0.45, 360+i*340, H*0.85], fill=(36,40,48), outline=(70,76,90), width=6)
    im=glow(im, W*0.82, H*0.3, 120, (255,80,60), 0.9); disc(im, W*0.82, H*0.3, 40, (255,120,90)); person(im, W*0.62, H*0.86, 420); person(im, W*0.72, H*0.86, 400); return im
@sc(1,"19c","Evara Tesh had kept the scroll","She had read it only twice.")
def _(im):
    im=canvas((12,12,20),(40,34,40)); im=glow(im, W*0.5, H*0.55, 280, (255,200,130), 0.8); d=ImageDraw.Draw(im)
    d.rectangle([W*0.3, H*0.6, W*0.7, H*0.63], fill=(220,200,150)); person(im, W*0.5, H*0.85, 520, "sit"); return im
@sc(1,"20","Kethran built the white halls out of crates.","Tell me what goes wrong.")
def _(im):
    im=canvas((14,14,18),(34,34,40)); d=ImageDraw.Draw(im)
    for i in range(12): x=200+(i%4)*370; y=H*0.55+(i//4)*170; d.rectangle([x,y,x+260,y+130], fill=(90,72,52), outline=(140,110,80), width=4)
    im=glow(im, W*0.5, H*0.3, 300, (255,220,170), 0.5); crowd(im, 150, W-150, H*0.5, 300, 6, 20); return im
@sc(1,"20","Nareth didn't touch the drives.","The cloud takes her.")
def _(im):
    stars(im, 500, 21); im=glow(im, W*0.5, H*0.5, 900, (120,90,170), 0.6); moon(im, W*0.5, H*0.5, 260, 20, (120,120,130))
    d=ImageDraw.Draw(im); d.arc([W*0.5-330, H*0.5-330, W*0.5+330, H*0.5+330], 0, 360, fill=(60,70,90), width=30); return im
@sc(1,"20b","On the bridge, Nareth cut the drive","For three breaths, nothing in the whole Orbiter was holding anyone down.")
def _(im):
    im=canvas((20,24,40),(60,60,90)); im=glow(im, W*0.5, H*0.18, 600, (255,255,240), 1.0); r=random.Random(22)
    for _ in range(26): person(im, r.randrange(150, W-150), r.randrange(int(H*0.45), int(H*0.9)), r.randrange(160, 240), r.choice(["stand","arms"]))
    return im
@sc(1,"20b","Twenty minutes.","At twenty-eight minutes, a spark came up out of the dark.")
def _(im):
    stars(im, 400, 23); moon(im, W*0.5, H*0.62, 620, 23, (120,120,130)); d=ImageDraw.Draw(im)
    d.arc([W*0.5-760, H*0.62-760, W*0.5+760, H*0.62+760], 200, 300, fill=(255,220,150), width=8); im=glow(im, W*0.2, H*0.42, 90, (255,220,150), 1.0)
    d=ImageDraw.Draw(im); d.rectangle([0, H*0.08, W, H*0.11], fill=(40,44,60)); crowd(im, 100, W-100, H*0.08, 120, 30, 23); return im
@sc(1,"21","Year 88","Now who's right.")
def _(im):
    im=canvas((18,20,28),(40,44,60)); d=ImageDraw.Draw(im); d.rectangle([0,H*0.82,W,H], fill=(20,20,26))
    for i in range(6): d.rectangle([60+i*300, H*0.2, 300+i*300, H*0.6], fill=(50,70,110))
    person(im, W*0.5, H*0.82, 820, "coat"); d=ImageDraw.Draw(im); d.polygon([(W*0.3,H*0.5),(W*0.7,H*0.47),(W*0.72,H*0.53),(W*0.3,H*0.56)], fill=INK); return im
@sc(1,"22","Okun · The valley","The sky woman was very stupid, and Okun liked her very much.")
def _(im):
    im=canvas((90,120,170),(200,190,150)); mountains(im, H*0.55, 260, 22, (70,80,90)); ground(im, H*0.75, (40,50,30))
    person(im, W*0.4, H*0.8, 560, "stand"); person(im, W*0.6, H*0.8, 300, "stand", facing=-1); return im
@sc(1,"23","**The sky.**","There's a shuttle three minutes away. Say the word.")
def _(im):
    im=canvas((10,12,20),(30,34,50)); rain(im); sea(im, H*0.72, (16,22,36), 23); d=ImageDraw.Draw(im)
    d.polygon([(W*0.25,H*0.72),(W*0.35,H*0.6),(W*0.65,H*0.6),(W*0.75,H*0.72)], fill=INK)
    for i in range(6): person(im, W*0.38+i*W*0.05, H*0.6, 170 if i not in (2,4) else 100, "arms" if i==1 else "stand")
    im=ship(im, W*0.6, H*0.18, 360); return im
@sc(1,"23",None,"Rising water.")
def _(im):
    im=canvas((8,10,18),(28,30,46)); im=glow(im, W*0.5, H*0.2, 200, (210,215,230), 0.6); moon(im, W*0.5, H*0.2, 110)
    mountains(im, H*0.55, 240, 24, (20,22,30)); sea(im, H*0.62, (18,26,44), 24); crowd(im, W*0.2, W*0.8, H*0.55, 90, 40, 24); return im

# ---------------- BOOK TWO ----------------
@sc(2,"01",None,"You watch. I'll walk.")
def _(im):
    im=canvas((70,90,120),(150,150,140)); sea(im, H*0.6, (40,56,70), 31); d=ImageDraw.Draw(im)
    d.line([(W*0.7,H*0.6),(W*0.7,H*0.35)], fill=INK, width=30); [d.line([(W*0.7,H*0.42),(W*0.7+dx,H*0.36)], fill=INK, width=12) for dx in (-120,100)]
    person(im, W*0.7, H*0.45, 120, "sit"); person(im, W*0.42, H*0.64, 300, "stand"); return im
@sc(2,"02","delicate as breath on glass","A pale green stain spreading, delicate as breath on glass.")
def _(im):
    stars(im, 500, 32); im=planet(im, W*0.5, H*0.62, 760); im=glow(im, W*0.42, H*0.56, 300, (90,200,120), 0.7)
    for i in range(4): im=ship(im, W*0.25+i*W*0.17, H*0.2+i*60, 220)
    return im
@sc(2,"03",None,"The mountain people.")
def _(im):
    im=canvas((50,60,90),(170,150,130)); mountains(im, H*0.6, 360, 33, (40,40,55)); ground(im, H*0.78, INK)
    crowd(im, 200, W-200, H*0.78, 300, 16, 33); return im
@sc(2,"03b",None,"The story of the water.")
def _(im):
    stars(im, 800, 34); ground(im, H*0.78); im=glow(im, W*0.5, H*0.76, 180, (255,170,90), 1.0)
    person(im, W*0.36, H*0.78, 330, "sit"); person(im, W*0.64, H*0.78, 300, "sit", facing=-1); return im
@sc(2,"04","colt","The skinny gray colt went first.")
def _(im):
    stars(im, 400, 35); im=planet(im, W*0.5, H*1.2, 1100); d=ImageDraw.Draw(im)
    d.polygon([(W*0.2,H*0.5),(W*0.8,H*0.5),(W*0.7,H*0.6),(W*0.3,H*0.6)], fill=(40,44,60)); d.polygon([(W*0.45,H*0.6),(W*0.55,H*0.6),(W*0.7,H*0.85),(W*0.3,H*0.85)], fill=(60,64,80))
    d.ellipse([W*0.47,H*0.7,W*0.55,H*0.74], fill=INK); d.line([(W*0.48,H*0.74),(W*0.48,H*0.78)], fill=INK, width=8); d.line([(W*0.54,H*0.74),(W*0.54,H*0.78)], fill=INK, width=8); return im
@sc(2,"05","lake","The first children sang by the lake.")
def _(im):
    im=canvas((30,40,80),(200,150,120)); mountains(im, H*0.55, 260, 36, (40,40,60)); sea(im, H*0.62, (50,70,100), 36, (180,180,200)); ground(im, H*0.82)
    crowd(im, 150, W-150, H*0.82, 200, 22, 36); return im
@sc(2,"06","The swing season opened","Two hundred people leaned over the rails, with cups, and argued.")
def _(im):
    im=canvas((10,10,16),(24,24,34)); moon(im, W*0.5, H*1.25, 1100, 37, (90,90,100)); d=ImageDraw.Draw(im)
    for k in range(3): d.rectangle([0,H*0.25+k*300,W,H*0.25+k*300+18], fill=(80,70,60)); crowd(im, 80, W-80, H*0.25+k*300, 150, 18, 37+k)
    im=glow(im, W*0.3, H*0.6, 50, (255,230,180), 1.0); return im
@sc(2,"07","reed","Nyra knew before anyone else could have known.")
def _(im):
    im=canvas((60,70,100),(200,170,120)); sea(im, H*0.72, (60,80,90), 38); d=ImageDraw.Draw(im)
    d.pieslice([W*0.3,H*0.45,W*0.7,H*0.95], 180, 360, fill=INK); person(im, W*0.5, H*0.86, 300, "stand"); return im
@sc(2,"08","Ruvan · The road","Ruvan went looking for the others.")
def _(im):
    im=canvas((90,90,120),(210,170,120)); mountains(im, H*0.6, 220, 39, (90,80,90)); ground(im, H*0.7, (60,50,40)); d=ImageDraw.Draw(im)
    d.polygon([(W*0.45,H*0.7),(W*0.55,H*0.7),(W*0.8,H),(W*0.2,H)], fill=(110,90,70)); person(im, W*0.5, H*0.8, 320); return im
@sc(2,"08b",None,"Kethran counted the shuttles, because counting was the only thing he could do.")
def _(im):
    stars(im, 600, 40); im=planet(im, W*0.5, H*0.45, 520); d=ImageDraw.Draw(im); d.rectangle([0,H*0.72,W,H], fill=INK)
    person(im, W*0.5, H*0.95, 700, "sit"); return im
@sc(2,"09",None,"Children of two worlds.")
def _(im):
    im=canvas((70,90,130),(190,170,140)); mountains(im, H*0.6, 280, 41, (60,60,80)); ground(im, H*0.8)
    person(im, W*0.3, H*0.8, 700); crowd(im, W*0.4, W*0.85, H*0.8, 240, 14, 41); return im
@sc(2,"10","The ship came in on a quiet night","A stranger stops at the edge of a firelight.")
def _(im):
    stars(im, 900, 42, 1.0); moon(im, W*0.3, H*0.7, 700, 42, (110,110,120)); im=ship(im, W*0.72, H*0.3, 200); return im
@sc(2,"11","dragon","You didn't ask for it either.")
def _(im):
    im=canvas((20,10,10),(70,40,30)); d=ImageDraw.Draw(im)
    for i in range(14): d.line([(W*0.08+i*W*0.065, H*0.15),(W*0.08+i*W*0.065, H*0.85)], fill=(30,26,24), width=14)
    d.polygon([(W*0.2,H*0.75),(W*0.5,H*0.45),(W*0.9,H*0.5),(W*0.7,H*0.75)], fill=(40,30,26)); d.polygon([(W*0.5,H*0.47),(W*0.3,H*0.25),(W*0.62,H*0.42)], fill=(40,30,26))
    person(im, W*0.5, H*0.86, 260, "kneel"); return im
@sc(2,"12",None,"The other gods.")
def _(im):
    stars(im, 400, 43); im=planet(im, W*0.5, H*0.7, 650); crowd(im, W*0.2, W*0.8, H*0.35, 220, 9, 43, (14,16,24)); return im
@sc(2,"13",None,"Gorun Vask, of the mountain people.")
def _(im):
    im=canvas((60,70,110),(180,160,140)); mountains(im, H*0.62, 300, 44, (50,50,70)); ground(im, H*0.8); person(im, W*0.5, H*0.8, 1100); person(im, W*0.66, H*0.8, 420); return im
@sc(2,"14","\"Not all of it,\" said a voice from above them.","A host who has been waiting up for guests who are late.")
def _(im):
    im=canvas((20,8,6),(80,30,16)); im=glow(im, W*0.5, H*0.85, 600, (255,90,40), 0.7); d=ImageDraw.Draw(im)
    d.rectangle([0,H*0.25,W,H*0.28], fill=(30,16,12)); person(im, W*0.5, H*0.25, 520, "coat", (90,90,95))
    for i in range(7): d.rectangle([80+i*240, H*0.55, 260+i*240, H*0.8], outline=(40,24,18), width=10)
    crowd(im, 150, W-150, H*0.92, 220, 10, 45); return im
@sc(2,"15","Atlantis","Set together so cleanly you couldn't fit a knife blade between them.")
def _(im):
    im=canvas((60,90,140),(220,190,140)); sea(im, H*0.62, (40,80,120), 46, (200,220,240)); d=ImageDraw.Draw(im)
    for k in range(3): r=700-k*200; d.ellipse([W*0.5-r, H*0.68-r*0.25, W*0.5+r, H*0.68+r*0.25], outline=(230,220,200), width=26)
    temple(im, W*0.5, H*0.66, 420, (60,50,46)); return im
@sc(2,"16","The rain had stopped.","Twenty-nine people on a roof in a drowned city, under the great gray eye.")
def _(im):
    im=canvas((12,16,30),(40,50,80)); stars(im, 200, 47, 0.4); im=glow(im, W*0.5, H*0.2, 300, (220,225,240), 0.8); moon(im, W*0.5, H*0.2, 170, 47)
    sea(im, H*0.6, (30,40,70), 47, (190,200,230)); d=ImageDraw.Draw(im); d.rectangle([W*0.25,H*0.58,W*0.75,H*0.62], fill=INK)
    crowd(im, W*0.28, W*0.72, H*0.6, 130, 22, 47); return im
@sc(2,"16","**Gast","The Old Builder turned back to his city.")
def _(im):
    im=canvas((10,12,22),(30,34,54)); rain(im); sea(im, H*0.75, (20,26,40), 48); temple(im, W*0.5, H*0.75, 900)
    person(im, W*0.5, H*0.75-900*0.07*6.2, 200); im=ship(im, W*0.75, H*0.25, 300); return im
@sc(2,"16b",None,"Varek's sliver under the ice.")
def _(im):
    im=canvas((180,200,220),(40,60,90)); d=ImageDraw.Draw(im); d.rectangle([0,H*0.4,W,H*0.45], fill=(230,240,250))
    im=glow(im, W*0.5, H*0.7, 260, (200,200,170), 0.8); person(im, W*0.5, H*0.95, 700, "coat"); return im
@sc(2,"17","dying","Sideways. Into the next room.")
def _(im):
    im=canvas((40,50,80),(150,130,120)); sea(im, H*0.65, (40,50,70), 49); ground(im, H*0.8, (30,28,30))
    person(im, W*0.4, H*0.85, 250, "sit"); person(im, W*0.58, H*0.85, 420, "kneel", facing=-1); return lights_rising(im, 6, 49, 0.75, 0.3)
@sc(2,"18","Hollis Dren had come himself","Nobody sat within ten paces of him.")
def _(im):
    im=canvas((12,12,18),(30,30,40)); d=ImageDraw.Draw(im); d.rectangle([0,H*0.6,W,H*0.63], fill=(40,36,40))
    crowd(im, 80, W*0.6, H*0.6, 230, 16, 50); person(im, W*0.85, H*0.6, 360, "sit", (90,90,96), -1); return im
@sc(2,"19","Yanna · The coast","You are not alone.")
def _(im):
    stars(im, 800, 51); sea(im, H*0.62, (16,24,40), 51); ground(im, H*0.8, (40,38,40)); person(im, W*0.5, H*0.82, 260, "sit"); return im
@sc(2,"19b","**Kael · Kemet","Snap out of it. You're not a god.")
def _(im):
    stars(im, 700, 52); im=glow(im, W*0.7, H*0.25, 160, (220,225,240), 0.6); moon(im, W*0.7, H*0.25, 80)
    ground(im, H*0.72, (20,16,12)); pyramid(im, W*0.42, H*0.72, 1100, (30,24,20)); d=ImageDraw.Draw(im); d.rectangle([W*0.65,H*0.66,W*0.95,H*0.72], fill=INK)
    person(im, W*0.74, H*0.66, 200); person(im, W*0.84, H*0.66, 220, facing=-1); return im
@sc(2,"19b","**Wren · A city on the inland sea","She's looking back.")
def _(im):
    stars(im, 400, 53); im=glow(im, W*0.6, H*0.22, 260, (220,225,240), 0.8); moon(im, W*0.6, H*0.22, 140)
    sea(im, H*0.6, (20,30,50), 53); d=ImageDraw.Draw(im); d.rectangle([0,H*0.66,W,H*0.72], fill=INK); person(im, W*0.4, H*0.66, 200, "sit"); return im
@sc(2,"19b","\"I think I have a solution,\" said Wren from the corner.","I think I have a solution.")
def _(im):
    im=canvas((14,14,20),(40,36,40)); im=glow(im, W*0.5, H*0.45, 260, (255,210,140), 0.7); d=ImageDraw.Draw(im)
    two_circles(im, W*0.5, H*0.35, 130, (240,235,220), 10); person(im, W*0.25, H*0.9, 420, "sit"); person(im, W*0.7, H*0.9, 560, facing=-1); return im
@sc(2,"20","Sael was waiting at the ship's hatch.","He was right.")
def _(im):
    stars(im, 500, 54); moon(im, W*0.5, H*1.2, 1000, 54, (90,90,100)); im=ship(im, W*0.5, H*0.4, 600)
    person(im, W*0.45, H*0.62, 160); person(im, W*0.53, H*0.62, 150); return im

# ---------------- BOOK THREE ----------------
@sc(3,"01",None,"The moon over London, ringing like a bell.")
def _(im):
    im=canvas((10,14,26),(40,50,80)); im=glow(im, W*0.6, H*0.25, 320, (220,225,240), 0.8); moon(im, W*0.6, H*0.25, 170)
    dome_city(im, int(H*0.7), 61, lights=4); d=ImageDraw.Draw(im); d.rectangle([W*0.1,H*0.08,W*0.9,H*0.9], outline=(20,20,26), width=40); return im
@sc(3,"02",None,"The watchers on the moon.")
def _(im):
    im=canvas((8,8,14),(20,20,30)); im=planet(im, W*0.5, H*0.4, 520); d=ImageDraw.Draw(im); d.rectangle([0,H*0.72,W,H], fill=INK)
    crowd(im, 200, W-200, H*0.95, 380, 11, 62); return im
@sc(3,"03","cedar","Buried under earth and stones.")
def _(im):
    im=canvas((20,16,12),(50,40,30)); im=glow(im, W*0.5, H*0.5, 360, (255,210,140), 0.7); d=ImageDraw.Draw(im)
    d.rectangle([W*0.3,H*0.45,W*0.7,H*0.6], fill=(90,60,36)); d.rectangle([W*0.36,H*0.42,W*0.64,H*0.5], fill=(150,150,145)); return im
@sc(3,"04","Outside, there was nothing at all.","Gate thirty-one: The Time Kael Was Right.")
def _(im):
    stars(im, 300, 63, 1.0); im=ring(im, W*0.5, H*0.45, 600, (160,200,255)); d=ImageDraw.Draw(im)
    d.line([(W*0.2,H*0.95),(W*0.42,H*0.6)], fill=(200,200,210), width=4); person(im, W*0.44, H*0.62, 160, "reach"); return im
@sc(3,"05",None,"The return to Dead Space.")
def _(im):
    stars(im, 200, 64, 1.0); im=well_merge(im); im=ring(im, W*0.5, H*0.75, 220); return im
@sc(3,"06","key","The bone-colored thing fit the door.")
def _(im):
    im=canvas((10,10,12),(24,22,24)); im=door(im, W*0.5, H*0.88, 700, 1300); im=glow(im, W*0.5, H*0.35, 90, (255,250,230), 1.0); return im
@sc(3,"07",None,"Thirty-eight gates, and Imra counted every one.")
def _(im):
    stars(im, 400, 65, 1.0)
    for k in range(7): im=ring(im, W*0.5, H*0.5, 700*(0.8**k), (150,190,255), 18, True)
    person(im, W*0.5, H*0.62, 120); return im
@sc(3,"08",None,"They had never been climbing.")
def _(im):
    im=canvas((8,8,12),(18,18,24)); d=ImageDraw.Draw(im); d.ellipse([W*0.25,H*0.55,W*0.75,H*0.7], fill=(30,30,36), outline=(90,90,100), width=8)
    d.line([(W*0.3,H*0.6),(W*0.45,H*0.66),(W*0.6,H*0.58)], fill=(150,150,160), width=4); return lights_rising(im, 40, 66, 0.6, 0.1)
@sc(3,"09","The last recording in the archive was the crossing itself.","Not sad. Not afraid. Only going on ahead.")
def _(im):
    im=canvas((20,16,24),(50,40,40)); im=glow(im, W*0.5, H*0.32, 520, (255,240,210), 1.0); d=ImageDraw.Draw(im)
    d.rounded_rectangle([W*0.38,H*0.15,W*0.62,H*0.5], radius=200, outline=(255,240,210), width=12); crowd(im, 60, W-60, H*0.85, 160, 70, 67); return im
@sc(3,"10",None,"The hunt fails.")
def _(im):
    im=canvas((8,8,12),(18,18,24)); im=sphere(im, W*0.5, H*0.4, 420); d=ImageDraw.Draw(im)
    d.line([(W*0.4,H*0.25),(W*0.55,H*0.5)], fill=(60,60,70), width=10); person(im, W*0.5, H*0.9, 420, "sit"); return im
@sc(3,"11",None,"You kept my chair.")
def _(im):
    im=canvas((10,10,16),(30,30,40)); im=ring(im, W*0.5, H*0.42, 520, (150,190,255)); ground(im, H*0.82, (24,24,30))
    person(im, W*0.47, H*0.82, 420); person(im, W*0.53, H*0.82, 400, facing=-1); return im
@sc(3,"12","And then it opened.","It's hollow. Elias was right.")
def _(im):
    stars(im, 600, 68); moon(im, W*0.5, H*0.7, 900, 68, (130,130,140)); d=ImageDraw.Draw(im)
    d.rectangle([W*0.38,H*0.33,W*0.62,H*0.45], fill=(255,214,140)); im=glow(im, W*0.5, H*0.39, 300, (255,214,140), 0.7); return ship(im, W*0.5, H*0.2, 220)
@sc(3,"13","**Kael · The islands","We're the only Aurelans who never were afraid.")
def _(im):
    im=canvas((90,140,180),(230,210,170)); sea(im, H*0.6, (40,100,140), 69, (230,240,250)); ground(im, H*0.82, (220,210,180))
    person(im, W*0.45, H*0.85, 380); person(im, W*0.55, H*0.85, 360, facing=-1); return im
@sc(3,"13b",None,"Nareth. You're late.")
def _(im):
    im=canvas((14,12,16),(40,34,36)); im=ring(im, W*0.5, H*0.45, 520, (150,190,255)); d=ImageDraw.Draw(im); d.rectangle([W*0.75,H*0.7,W*0.95,H*0.76], fill=(40,30,24))
    person(im, W*0.82, H*0.88, 400); return im
@sc(3,"14","It sat at the center of the ring","Just a crack. Just enough to look through.")
def _(im):
    im=canvas((6,8,12),(18,20,28)); im=sphere(im, W*0.5, H*0.42, 520); d=ImageDraw.Draw(im); d.rectangle([0,H*0.8,W,H*0.82], fill=(40,46,60))
    person(im, W*0.35, H*0.8, 220); person(im, W*0.62, H*0.8, 220); return im
@sc(3,"15",None,"The door opened for nine seconds.")
def _(im):
    im=canvas((4,4,8),(10,10,16)); im=sphere(im, W*0.5, H*0.45, 520, opened=True)
    for k in range(6): im=planet(im, W*0.5+(k-2.5)*170, H*0.45+(k%2)*60, 60)
    return im
@sc(3,"16","A city on a plain under a sky the wrong color.","A single window, burning in the dark.")
def _(im):
    im=canvas((40,20,60),(90,50,100)); dome_city(im, int(H*0.82), 70); im=tower(im, W*0.7, H*0.82, 200, 1300, window=200); return im
@sc(3,"17","The chamber at the heart of the mountain was cold","Velira screamed.")
def _(im):
    im=canvas((4,6,12),(14,16,24)); im=sphere(im, W*0.5, H*0.38, 520, opened=True); d=ImageDraw.Draw(im); d.rectangle([0,H*0.78,W,H*0.8], fill=(50,56,70))
    person(im, W*0.5, H*0.78, 380, "coat"); return im
@sc(3,"17b",None,"Then he threw it in.")
def _(im):
    im=canvas((10,6,4),(30,16,10)); im=glow(im, W*0.62, H*0.6, 300, (255,120,40), 1.0); d=ImageDraw.Draw(im)
    d.rectangle([W*0.52,H*0.48,W*0.72,H*0.72], outline=(60,40,30), width=20); person(im, W*0.38, H*0.85, 600, "reach"); return im
@sc(3,"18","Onto a dark room.","The man in the first seat lifted his head.")
def _(im):
    im=canvas((6,6,10),(16,16,22)); im=door(im, W*0.5, H*0.88, 900, 1500, (120,140,200)); im=sphere(im, W*0.5, H*0.45, 220)
    person(im, W*0.5, H*0.8, 360, "sit"); return im
@sc(3,"19","**Step seventeen.**","Have we met?")
def _(im):
    im=canvas((60,50,80),(220,150,100)); dome_city(im, int(H*0.8), 71, (60,40,40)); ground(im, H*0.72, INK); d=ImageDraw.Draw(im)
    peak(im, W*0.3, H*0.72, 700, 200); person(im, W*0.25, H*0.72-180, 300, "sit"); person(im, W*0.36, H*0.72-170, 300, "sit", facing=-1); return im
@sc(3,"19","**Step thirty-eight.**","Two more. Come in, come in. There's soup.")
def _(im):
    stars(im, 500, 72); ground(im, H*0.75, INK); d=ImageDraw.Draw(im); d.polygon([(W*0.25,H*0.75),(W*0.25,H*0.55),(W*0.5,H*0.42),(W*0.75,H*0.55),(W*0.75,H*0.75)], fill=(20,18,20))
    d.rectangle([W*0.45,H*0.6,W*0.55,H*0.68], fill=(255,210,140)); im=glow(im, W*0.5, H*0.64, 200, (255,200,120), 0.8); person(im, W*0.5, H*0.86, 300); return im
@sc(3,"20","**Sael · Step forty-one.**","Two hundred and thirteen men with the same face, asleep.")
def _(im):
    im=canvas((40,32,10),(90,70,30)); cradles(im, H*0.88, 5, (120,110,80)); im=glow(im, W*0.5, H*0.2, 400, (255,230,160), 0.6); person(im, W*0.5, H*0.95, 260); return im
@sc(3,"20","There were no weapons in the hall.","Cradles. Tip them. Make a wall.")
def _(im):
    im=canvas((40,32,10),(80,64,30)); d=ImageDraw.Draw(im); d.rectangle([0,H*0.7,W,H*0.76], fill=(110,100,70))
    crowd(im, 80, W-80, H*0.7, 260, 16, 73); crowd(im, 200, W-200, H*0.5, 200, 10, 74, (220,210,190)); return im
@sc(3,"21",None,"Evenings. One for every evening at the window.")
def _(im):
    im=canvas((50,24,70),(100,60,110)); im=tower(im, W*0.5, H*0.95, 400, 1700, window=260); return im
@sc(3,"22","Halia Brenn was sitting on the low wall.","I've just chosen to die. And I've never felt so alive.")
def _(im):
    stars(im, 600, 75); mountains(im, H*0.62, 260, 75, (30,32,50)); ground(im, H*0.78); d=ImageDraw.Draw(im); d.rectangle([W*0.15,H*0.74,W*0.85,H*0.78], fill=(20,20,26))
    person(im, W*0.42, H*0.74, 300, "sit"); person(im, W*0.58, H*0.74, 310, "sit", facing=-1); return im
@sc(3,"23",None,"Rhaen Sol stood alone, with her hands folded.")
def _(im):
    im=canvas((8,8,14),(24,24,34)); im=ship(im, W*0.5, H*0.25, 1200); ground(im, H*0.8, (30,30,36)); person(im, W*0.5, H*0.8, 360, "coat"); return im
@sc(3,"24","Wade Ruskin stood at the door.","Every plan needs one road nobody wrote down.")
def _(im):
    im=canvas((60,40,30),(200,140,90)); mountains(im, H*0.62, 160, 76, (60,40,40)); ground(im, H*0.72, (40,30,24)); d=ImageDraw.Draw(im)
    d.polygon([(W*0.48,H*0.72),(W*0.52,H*0.72),(W*0.9,H),(W*0.1,H)], fill=(90,70,50)); return glow(im, W*0.5, H*0.73, 30, (255,240,200), 1.0)
@sc(3,"25","**Hannah","She hasn't laughed yet. She hasn't rolled over.")
def _(im):
    im=canvas((40,50,70),(140,150,170)); dome_city(im, int(H*0.8), 77, (50,50,60)); d=ImageDraw.Draw(im)
    d.rectangle([W*0.15,H*0.1,W*0.85,H*0.85], outline=(20,20,24), width=60); d.line([(W*0.5,H*0.1),(W*0.5,H*0.85)], fill=(20,20,24), width=30)
    person(im, W*0.5, H*0.92, 700, "stand"); return im
@sc(3,"25","He moved so fast that Kael barely saw it.","Two men with the same face, fighting over a stone.")
def _(im):
    im=canvas((4,6,12),(12,14,22)); im=sphere(im, W*0.5, H*0.3, 520, opened=True); d=ImageDraw.Draw(im); d.rectangle([0,H*0.72,W,H*0.74], fill=(60,66,80))
    person(im, W*0.42, H*0.72, 380, "reach"); person(im, W*0.58, H*0.72, 380, "reach", (200,170,90), -1); im=glow(im, W*0.5, H*0.6, 80, (255,250,220), 1.0); return im
@sc(3,"25b","**Varek · Under the mountain","A god should always have somewhere to stand.")
def _(im):
    im=canvas((6,6,10),(16,16,22)); im=glow(im, W*0.5, H*0.6, 500, (200,200,255), 0.4); d=ImageDraw.Draw(im)
    d.ellipse([W*0.1,H*0.35,W*0.9,H*0.85], outline=(180,190,255), width=6); person(im, W*0.5, H*0.75, 300); return im
@sc(3,"26",None,"You took your time.")
def _(im):
    im=canvas((100,150,210),(240,220,170)); mountains(im, H*0.6, 220, 78, (90,110,90)); peak(im, W*0.5, H, 1500, 700, (60,70,60))
    person(im, W*0.44, H-700+6, 200, "sit"); person(im, W*0.54, H-700+6, 200, "sit", facing=-1)
    d=ImageDraw.Draw(im); d.arc([W*0.6,H*0.15,W*0.95,H*0.3], 200, 330, fill=(255,255,255), width=4); return im
@sc(3,"26","Further along, in the long grass","You can stop catching me now. I'm home.")
def _(im):
    im=canvas((140,180,220),(240,230,190)); ground(im, H*0.7, (90,120,70)); crowd(im, 150, W-150, H*0.85, 200, 41, 79, (50,60,40)); return im
@sc(3,"26b",None,"He was the only thing in the universe that still had a floor.")
def _(im):
    im=canvas((0,0,2),(4,4,8)); im=lights_rising(im, 260, 80, 0.98, 0.02); d=ImageDraw.Draw(im)
    d.polygon([(W*0.3,H*0.55),(W*0.7,H*0.55),(W*0.6,H*0.7),(W*0.4,H*0.7)], fill=(40,30,24)); d.rectangle([W*0.44,H*0.47,W*0.56,H*0.55], fill=(60,60,66))
    return glow(im, W*0.5, H*0.5, 40, (255,214,150), 1.0)
