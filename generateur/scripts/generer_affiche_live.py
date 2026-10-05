#!/usr/bin/env python3
"""
Générateur de stories « MATCH EN DIRECT » — Le Crès Volley-Ball.
Respecte la charte graphique du club (couleurs, Big Shoulders / Geist Mono,
fond anthracite + balayage + halo + filigrane + grain + vignettage,
zones de sécurité story, alignement sur ligne de base, avance typographique).

Usage simple :
  python generer_affiche_live.py --adversaire "LA CROIX D'ARGENT" \
      --competition "RÉGIONALE 1 FÉMININE" --date 2026-10-04 --heure 14:00 \
      --out /mnt/user-data/outputs

Usage par lot (un week-end entier) :
  python generer_affiche_live.py --json matchs.json --out /mnt/user-data/outputs
  (matchs.json = liste d'objets avec les mêmes clés que les options longues)
"""
import argparse, json, math, os, re, sys, unicodedata
from datetime import date
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(SKILL_DIR, "assets", "fonts")
LOGO_DIR = os.path.join(SKILL_DIR, "assets", "logos")

# --- Palette (charte §1) ------------------------------------------------------
INK = (240, 96, 160)          # rose principal
ROSE_CLAIR = (255, 190, 224)  # texte secondaire
BG_TOP = (12, 11, 13)         # #0C0B0D
BG_BOT = (30, 20, 26)         # #1E141A
WHITE = (255, 255, 255)       # réservé à Le Crès / texte principal
NEUTRE = (150, 148, 152)      # autres clubs

JOURS = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"]
MOIS = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET",
        "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]

ABREVIATIONS = {  # charte §6 : jamais de codes abrégés
    r"\bRG1\b": "RÉGIONALE M 1", r"\bRG2\b": "RÉGIONALE M 2",
    r"\bRF1\b": "RÉGIONALE F 1", r"\bRF2\b": "RÉGIONALE F 2",
    r"\bPNM\b": "PRÉNATIONALE MASCULINE", r"\bPNG\b": "PRÉNATIONALE MASCULINE",
    r"\bPNF\b": "PRÉNATIONALE FÉMININE",
    r"\bM(\d{2})\b": r"M \1",
}


# --- Typo ---------------------------------------------------------------------
@lru_cache(maxsize=None)
def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"{name}.ttf"), int(size))


def text_width(f, text, tracking=0):
    """Largeur via l'avance typographique réelle (getlength), jamais la bbox."""
    if not text:
        return 0
    if tracking == 0:
        return f.getlength(text)
    return sum(f.getlength(c) for c in text) + tracking * (len(text) - 1)


def draw_text(draw, x, baseline, text, f, fill, align="m", tracking=0):
    """Dessine sur une ligne de base commune (anchor 'ls') — les É/È ne coulent pas."""
    w = text_width(f, text, tracking)
    x0 = x - w / 2 if align == "m" else (x - w if align == "r" else x)
    if tracking == 0:
        draw.text((x0, baseline), text, font=f, fill=fill, anchor="ls")
    else:
        cx = x0
        for c in text:
            draw.text((cx, baseline), c, font=f, fill=fill, anchor="ls")
            cx += f.getlength(c) + tracking
    return w


def fit_size(name, text, max_w, size, min_size=10, tracking=0):
    while size > min_size and text_width(font(name, size), text, tracking) > max_w:
        size -= 2
    return size


def wrap_two_lines(name, text, max_w, size, min_size, tracking=0):
    """Taille unique sur une ligne si possible, sinon coupe en deux lignes équilibrées."""
    s = fit_size(name, text, max_w, size, min_size, tracking)
    if s >= size * 0.8 or len(text.split()) < 2:
        return s, [text]
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        w = max(text_width(font(name, size), a, tracking), text_width(font(name, size), b, tracking))
        if best is None or w < best[0]:
            best = (w, [a, b])
    lines = best[1] if best else [text]
    s = size
    while s > min_size and max(text_width(font(name, s), l, tracking) for l in lines) > max_w:
        s -= 2
    return s, lines


# --- Logos --------------------------------------------------------------------
def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def compact(s):
    return re.sub(r"[^a-z0-9]", "", slug(s))


def find_club(nom):
    """Fiche du club (fichier, nom, court, alias) trouvée par alias dans clubs.json, ou None."""
    idx = os.path.join(LOGO_DIR, "clubs.json")
    if not os.path.exists(idx):
        return None
    target, tokens = compact(nom), set(slug(nom).split("-"))
    best = None
    for club in json.load(open(idx, encoding="utf-8")):
        for al in club["alias"] + [club["nom"], club["fichier"].rsplit(".", 1)[0]]:
            c = compact(al)
            if not c:
                continue
            ok = (c in tokens) if len(c) <= 4 else (c in target or (len(target) >= 5 and target in c))
            if ok and (best is None or len(c) > best[0]):
                best = (len(c), club)
    return best[1] if best else None


def find_club_logo(explicit, nom):
    if explicit and os.path.exists(explicit):
        return explicit
    club = find_club(nom)
    return os.path.join(LOGO_DIR, club["fichier"]) if club else None


def load_logo(path):
    """Charge un logo ; si pas de vraie transparence, détoure le fond clair relié aux bords."""
    im = Image.open(path).convert("RGBA")
    alpha = np.array(im.split()[3])
    if (alpha < 250).mean() < 0.01:  # pas de transparence -> détourage du fond blanc
        rgb = im.convert("RGB")
        key = (1, 254, 1)
        w, h = rgb.size
        for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
            if sum(rgb.getpixel(seed)) > 690:
                ImageDraw.floodfill(rgb, seed, key, thresh=45)
        arr = np.array(rgb)
        mask = np.all(arr == key, axis=-1)
        a = np.where(mask, 0, 255).astype(np.uint8)
        a_img = Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8))
        im = Image.open(path).convert("RGBA")
        im.putalpha(a_img)
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def initials(name):
    stop = {"LA", "LE", "LES", "DE", "DU", "DES", "D", "L", "ET", "VB", "VOLLEY", "BALL", "CLUB", "ASSOCIATION"}
    words = [w for w in re.split(r"[\s'’\-]+", name.upper()) if w and w not in stop]
    return "".join(w[0] for w in words[:3]) or name[:2].upper()


def pastille(img, cx, cy, r, logo=None, lecres=False, label=""):
    """Disque blanc cerclé de rose avec logo (charte §4)."""
    d = ImageDraw.Draw(img)
    ring = max(4, int(r * 0.07))
    # ombre douce
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - r, cy - r + 10, cx + r, cy + r + 10], fill=(0, 0, 0, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)
    d.ellipse([cx - r + ring, cy - r + ring, cx + r - ring, cy + r - ring], fill=WHITE)
    inner = r - ring
    if logo is not None:
        a = np.array(logo.split()[3]) > 40
        ys, xs = np.nonzero(a)
        if len(xs):
            ext = np.sqrt((xs - logo.width / 2) ** 2 + (ys - logo.height / 2) ** 2).max()
        else:
            ext = max(logo.size) / 2
        k = inner * 0.86 / ext  # logos ronds -> ~86 % du disque, formes carrées -> inscrites
        lg = logo.resize((max(1, int(logo.width * k)), max(1, int(logo.height * k))), Image.LANCZOS)
        img.alpha_composite(lg, (int(cx - lg.width / 2), int(cy - lg.height / 2)))
    else:
        if lecres:
            s = fit_size("BigShoulders-Bold", "LE CRÈS", inner * 1.55, inner * 0.62)
            draw_text(d, cx, cy + s * 0.12, "LE CRÈS", font("BigShoulders-Bold", s), INK)
            fs = fit_size("BigShoulders-Regular", "VOLLEY-BALL", inner * 1.25, s * 0.38, 6, 2)
            draw_text(d, cx, cy + s * 0.12 + fs * 1.2, "VOLLEY-BALL", font("BigShoulders-Regular", fs), INK, tracking=2)
        else:
            txt = initials(label)
            s = fit_size("BigShoulders-Bold", txt, inner * 1.3, inner * 0.95)
            draw_text(d, cx, cy + s * 0.35, txt, font("BigShoulders-Bold", s), NEUTRE)


# --- Fond (charte §3) ----------------------------------------------------------
def background(W, H, watermark=None):
    y = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array(BG_TOP, float), np.array(BG_BOT, float)
    arr = np.broadcast_to(top + (bot - top) * y, (H, W, 3)).copy()
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")

    # balayage diagonal rose
    sweep = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sweep).polygon([(W * 0.15, -H * 0.1), (W * 0.55, -H * 0.1), (W * 0.05, H * 1.1), (-W * 0.35, H * 1.1)], fill=255)
    sweep = sweep.filter(ImageFilter.GaussianBlur(W * 0.12))
    layer = Image.new("RGBA", (W, H), INK + (0,))
    layer.putalpha(sweep.point(lambda v: int(v * 0.07)))
    img.alpha_composite(layer)

    # halo radial
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy = W * 0.5, H * 0.45
    dist = np.sqrt(((xx - cx) / (W * 0.75)) ** 2 + ((yy - cy) / (H * 0.5)) ** 2)
    halo = np.clip(1 - dist, 0, 1) ** 2 * 0.10
    layer = Image.new("RGBA", (W, H), INK + (0,))
    layer.putalpha(Image.fromarray((halo * 255).astype(np.uint8)))
    img.alpha_composite(layer)

    # filigrane logo, centré, ~8 %
    if watermark is not None:
        wm = ImageOps.contain(watermark, (int(W * 0.95), int(H * 0.55)), Image.LANCZOS)
        a = wm.split()[3].point(lambda v: int(v * 0.07))
        wm.putalpha(a)
        img.alpha_composite(wm, (int((W - wm.width) / 2), int(H * 0.5 - wm.height / 2)))
    return img


def finish(img):
    """Grain fin + grain grossier + vignettage (charte §3.5-6)."""
    W, H = img.size
    rgb = np.array(img.convert("RGB")).astype(float)
    rng = np.random.default_rng(7)
    fine = rng.normal(0, 5.0, (H, W, 1))
    coarse = rng.normal(0, 1, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    coarse = np.array(Image.fromarray(coarse).resize((W, H), Image.BILINEAR))[:, :, None] * 3.0
    rgb += fine + coarse
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    rgb *= (1 - 0.38 * np.clip(d - 0.35, 0, 1) / 0.65)[:, :, None]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


# --- Éléments -----------------------------------------------------------------
def rounded(img, box, radius, fill=None, outline=None, width=2):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius, fill=fill, outline=outline, width=width)
    img.alpha_composite(layer)


def live_pill(img, cx, top, h, text="EN DIRECT SUR YOUTUBE"):
    f = font("GeistMono-Bold", h * 0.42)
    tw = text_width(f, text, 2)
    dot = h * 0.22
    w = tw + dot * 2 + h * 1.0
    x0 = cx - w / 2
    rounded(img, [x0, top, x0 + w, top + h], h / 2, fill=INK + (255,))
    d = ImageDraw.Draw(img)
    dx = x0 + h * 0.45 + dot / 2
    d.ellipse([dx - dot / 2, top + h / 2 - dot / 2, dx + dot / 2, top + h / 2 + dot / 2], fill=WHITE)
    draw_text(d, dx + dot / 2 + h * 0.25, top + h / 2 + f.size * 0.36, text, f, WHITE, align="l", tracking=2)


def cta_pill(img, cx, top, h, text):
    f = font("BigShoulders-Bold", h * 0.6)
    tw = text_width(f, text, 3)
    tri = h * 0.32
    w = tw + tri + h * 1.4
    x0 = cx - w / 2
    rounded(img, [x0, top, x0 + w, top + h], h / 2, fill=INK + (255,))
    d = ImageDraw.Draw(img)
    tx = x0 + h * 0.6
    ty = top + h / 2
    d.polygon([(tx, ty - tri / 2), (tx, ty + tri / 2), (tx + tri * 0.9, ty)], fill=WHITE)
    draw_text(d, tx + tri + h * 0.22, top + h / 2 + f.size * 0.35, text, f, WHITE, align="l", tracking=3)


def normalise(s):
    s = s.upper().strip()
    for pat, rep in ABREVIATIONS.items():
        s = re.sub(pat, rep, s)
    return s


def date_fr(iso):
    d = date.fromisoformat(iso)
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def heure_fr(h):
    hh, mm = (h.replace("h", ":").replace("H", ":").split(":") + ["00"])[:2]
    return f"{int(hh)}H{int(mm or 0):02d}"


# --- Gabarits -----------------------------------------------------------------
LAYOUTS = {
    # story 9:16 — rien d'important dans y<230 ni y>1670 (charte §5C).
    # La zone sticker (y 1490-1610) reste vide : le sticker « lien » Instagram y est posé à la main.
    "story": dict(W=1080, H=1920, pill=(268, 62), kicker=392, t1=(586, 186), t2=(762, 186), filet=806,
                  pcy=930, r=92, names=1112, card=(1150, 1408), comp=1212, date=(1310, 92), time=(1384, 70),
                  appel=1482, sticker=(1505, 1615), foot=1650, safe=(230, 1670)),
}


def render(m, out_dir, fmt="story"):
    L = LAYOUTS[fmt]
    W, H = L["W"], L["H"]
    lecres_path = find_club_logo(m.get("logo_lecres"), "le cres")
    adv_path = find_club_logo(m.get("logo_adversaire"), m["adversaire"])
    lg_lecres = load_logo(lecres_path) if lecres_path else None
    lg_adv = load_logo(adv_path) if adv_path else None
    fil = os.path.join(LOGO_DIR, "filigrane-renard.png")
    wm = Image.open(fil).convert("RGBA") if os.path.exists(fil) else lg_lecres

    img = background(W, H, wm)
    d = ImageDraw.Draw(img)
    cx, M = W / 2, 70

    live_pill(img, cx, L["pill"][0], L["pill"][1], m.get("bandeau", "EN DIRECT SUR YOUTUBE"))
    kick = m.get("kicker", "LE CRÈS VOLLEY-BALL · SAISON 2026 - 2027")
    ks = fit_size("BigShoulders-Regular", kick, W - 2 * M, 40, 20, 3)
    draw_text(d, cx, L["kicker"], kick, font("BigShoulders-Regular", ks), ROSE_CLAIR, tracking=3)

    t1, t2 = m.get("titre1", "MATCH"), m.get("titre2", "EN DIRECT")
    s = min(fit_size("BigShoulders-Bold", t1, W - 2 * M, L["t1"][1], 60, -2),
            fit_size("BigShoulders-Bold", t2, W - 2 * M, L["t2"][1], 60, -2))
    draw_text(d, cx, L["t1"][0], t1, font("BigShoulders-Bold", s), WHITE, tracking=-2)
    draw_text(d, cx, L["t2"][0], t2, font("BigShoulders-Bold", s), INK, tracking=-2)
    rounded(img, [M + 60, L["filet"], W - M - 60, L["filet"] + 2], 1, fill=INK + (150,))

    # affiche : équipe qui reçoit à gauche
    home = m.get("domicile", True)
    lec = dict(name="LE CRÈS", logo=lg_lecres, lecres=True)
    club = find_club(m["adversaire"])
    nom_aff = m.get("nom_affiche") or (club.get("court") if club and not m.get("logo_adversaire") else None)
    if not nom_aff:  # nom FFVB brut : on retire les mentions génériques (« VOLLEY-BALL GRUISSAN » -> « GRUISSAN »)
        brut = normalise(m["adversaire"])
        net = re.sub(r"^(?:(?:VOLLEY[ -]?BALL|VOLLEY|VB|CLUB|ASSOCIATION)\s+)+|(?:\s+(?:VOLLEY[ -]?BALL|VOLLEY|VB|CLUB))+$", "", brut).strip()
        nom_aff = net or brut
    adv = dict(name=normalise(nom_aff), logo=lg_adv, lecres=False)
    left, right = (lec, adv) if home else (adv, lec)
    xs = [W * 0.25, W * 0.75]
    for team, x in zip([left, right], xs):
        r = L["r"] * (1.3 if team["lecres"] else 1.0)
        pastille(img, x, L["pcy"], r, team["logo"], team["lecres"], team["name"])
    d = ImageDraw.Draw(img)
    vs = font("BigShoulders-Bold", L["r"] * 1.0)
    draw_text(d, cx, L["pcy"] + vs.size * 0.36, "VS", vs, INK, tracking=2)
    nmax = W * 0.42
    for team, x in zip([left, right], xs):
        col = WHITE if team["lecres"] else ROSE_CLAIR
        sz, lines = wrap_two_lines("BigShoulders-Bold", team["name"], nmax, 50, 26, 1)
        if len(lines) == 1:
            draw_text(d, x, L["names"], lines[0], font("BigShoulders-Bold", sz), col, tracking=1)
        else:
            sz2 = min(sz, 38)
            for i, ln in enumerate(lines):
                draw_text(d, x, L["names"] - sz2 * 0.75 + i * sz2 * 1.08, ln, font("BigShoulders-Bold", sz2), col, tracking=1)

    # carte d'info
    y0, y1 = L["card"]
    rounded(img, [M, y0, W - M, y1], 34, fill=(255, 255, 255, 18), outline=INK + (200,), width=3)
    d = ImageDraw.Draw(img)
    comp = normalise(m["competition"])
    cs = fit_size("BigShoulders-Bold", comp, W - 2 * M - 80, 46, 24, 3)
    draw_text(d, cx, L["comp"], comp, font("BigShoulders-Bold", cs), INK, tracking=3)
    dt = date_fr(m["date"])
    ds = fit_size("BigShoulders-Bold", dt, W - 2 * M - 80, L["date"][1], 40, 1)
    draw_text(d, cx, L["date"][0], dt, font("BigShoulders-Bold", ds), WHITE, tracking=1)
    hr = heure_fr(m["heure"])
    draw_text(d, cx, L["time"][0], hr, font("GeistMono-Bold", L["time"][1]), INK)

    # appel vers le sticker lien (ajouté à la main dans Instagram, juste en dessous)
    appel = m.get("appel", "CLIQUE SUR LE LIEN POUR SUIVRE LE LIVE")
    fa = font("GeistMono-Bold", fit_size("GeistMono-Bold", appel, W - 2 * M - 120, 30, 18, 1))
    tw = draw_text(d, cx, L["appel"], appel, fa, ROSE_CLAIR, tracking=1)
    tri = fa.size * 0.55
    for sx in (cx - tw / 2 - tri - 18, cx + tw / 2 + 18):
        ty = L["appel"] - fa.size * 0.55
        d.polygon([(sx, ty - tri / 2), (sx + tri, ty - tri / 2), (sx + tri / 2, ty + tri / 2)], fill=INK)

    d = ImageDraw.Draw(img)
    lieu = normalise(m.get("lieu", "GYMNASE JEAN MOULIN · LE CRÈS"))
    fs = fit_size("GeistMono-Regular", lieu, W - 2 * M - 80, 26, 16)
    f = font("GeistMono-Regular", fs)
    pr = 26
    tw = text_width(f, lieu)
    gx = cx - (tw + pr * 2 + 16) / 2
    pastille(img, gx + pr, L["foot"] - fs * 0.35, pr, lg_lecres, True)
    d = ImageDraw.Draw(img)
    draw_text(d, gx + pr * 2 + 16, L["foot"], lieu, f, ROSE_CLAIR, align="l")

    out = finish(img)
    os.makedirs(out_dir, exist_ok=True)
    name = f"live_{m['date'].replace('-', '')}_{slug(m['adversaire'])}_story.png"
    path = os.path.join(out_dir, name)
    out.save(path, "PNG", optimize=True)
    return path, bool(lg_lecres), bool(lg_adv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="fichier JSON : un match (objet) ou une liste de matchs")
    ap.add_argument("--ffvb", help="texte copié d'une page FFVB : matchs du Crès à domicile à partir de --depuis")
    ap.add_argument("--url", help="adresse du data/matchs.json publié par la GitHub Action (raw.githubusercontent.com)")
    ap.add_argument("--weekend", action="store_true", help="ne garder que le prochain week-end (ou celui en cours)")
    ap.add_argument("--tous", action="store_true", help="avec --url/--ffvb : garder aussi l'extérieur")
    ap.add_argument("--depuis", default=date.today().isoformat())
    ap.add_argument("--jusqu-a", dest="jusqua")
    ap.add_argument("--adversaire")
    ap.add_argument("--competition")
    ap.add_argument("--date", help="AAAA-MM-JJ")
    ap.add_argument("--heure", help="HH:MM")
    ap.add_argument("--exterieur", action="store_true", help="match à l'extérieur (adversaire à gauche)")
    ap.add_argument("--lieu")
    ap.add_argument("--logo-lecres")
    ap.add_argument("--logo-adversaire")
    ap.add_argument("--appel", help="texte au-dessus de la zone du sticker lien")
    ap.add_argument("--kicker")
    ap.add_argument("--out", default="/mnt/user-data/outputs")
    a = ap.parse_args()

    if not (a.url or a.ffvb or a.json or a.adversaire):
        src = os.path.join(SKILL_DIR, "assets", "source.json")
        if os.path.exists(src):
            a.url = json.load(open(src, encoding="utf-8")).get("url") or None
        if not a.url:
            sys.exit("Aucune source : renseigner l'URL dans assets/source.json ou passer --url / --ffvb / --adversaire.")

    if a.weekend:
        from datetime import timedelta
        t = date.today()
        sam = t + timedelta(days=(5 - t.weekday()) % 7) if t.weekday() < 5 else t - timedelta(days=t.weekday() - 5)
        a.depuis, a.jusqua = max(t, sam).isoformat(), (sam + timedelta(days=1)).isoformat()

    def garder(m):
        adv = str(m.get("adversaire", "")).strip()
        if not adv or re.fullmatch(r"[xX]+|EXEMPT.*|-+", adv):  # adversaire inconnu / exempt
            return False
        return ((a.tous or m.get("domicile", True)) and not m.get("joue")
                and a.depuis <= m["date"] and (not a.jusqua or m["date"] <= a.jusqua))

    if a.url:
        import urllib.request
        req = urllib.request.Request(a.url, headers={"Cache-Control": "no-cache"})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        if isinstance(data, dict):
            if data.get("erreurs"):
                print("⚠ erreurs signalées par la récupération : " + " ; ".join(data["erreurs"]), file=sys.stderr)
            print(f"matchs.json mis à jour le {data.get('mis_a_jour', '?')}", file=sys.stderr)
            data = data.get("matchs", [])
        matchs = [m for m in data if garder(m)]
        if not matchs:
            sys.exit(f"Aucun match du Crès à domicile entre {a.depuis} et {a.jusqua or '…'}.")
        for m in matchs:
            print(f"- {m['date']} {m['heure']} · {m['competition']} · vs {m['adversaire']}", file=sys.stderr)
    elif a.ffvb:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from lire_ffvb import lire
        matchs = [m for m in lire(open(a.ffvb, encoding="utf-8").read(), "2026/2027") if garder(m)]
        if not matchs:
            sys.exit("Aucun match du Crès à domicile dans la période demandée.")
    elif a.json:
        data = json.load(open(a.json, encoding="utf-8"))
        matchs = data if isinstance(data, list) else [data]
    else:
        if not all([a.adversaire, a.competition, a.date, a.heure]):
            sys.exit("Il faut --adversaire, --competition, --date et --heure (ou --json).")
        matchs = [{k: v for k, v in dict(
            adversaire=a.adversaire, competition=a.competition, date=a.date, heure=a.heure,
            domicile=not a.exterieur, lieu=a.lieu, logo_lecres=a.logo_lecres,
            logo_adversaire=a.logo_adversaire, appel=a.appel, kicker=a.kicker).items() if v is not None}]

    for m in matchs:
        if "exterieur" in m:
            m["domicile"] = not m.pop("exterieur")
        p, has_l, has_a = render(m, a.out)
        warn = []
        if not has_l:
            warn.append("logo Le Crès absent (médaillon texte)")
        if not has_a:
            warn.append("logo adversaire absent (initiales)")
        print(p + ("  ⚠ " + " ; ".join(warn) if warn else ""))


if __name__ == "__main__":
    main()
