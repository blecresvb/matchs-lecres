#!/usr/bin/env python3
"""
Lit le texte copié depuis une page calendrier/résultats du site FFVB (ffvbbeach.org,
Ctrl+A puis Ctrl+C) et en extrait les matchs du Crès sous forme de JSON pour
generer_affiche_live.py.

  python lire_ffvb.py page.txt                      # matchs à domicile à partir d'aujourd'hui
  python lire_ffvb.py page.txt --depuis 2026-10-10 --jusqu-a 2026-10-11
  python lire_ffvb.py page.txt --tous               # domicile + extérieur
  python lire_ffvb.py page.txt -o matchs.json
"""
import argparse, json, re, sys
from datetime import date

CLUB = re.compile(r"\bLE\s+CR[EÈ]S\b", re.I)
ENTETE = re.compile(r"^\s*([A-Z0-9]{2,4})\s+-\s+(.+?)\s*(?:\t|Tableau de la comp|$)")
LIGNE = re.compile(r"^\s*\w+\t([A-Z0-9]{2,4}\d{3})\t(\d{2})/(\d{2})(?:/(\d{2,4}))?\t(\d{1,2}[:hH]\d{2})\t(.*)$")


def competition_propre(libelle):
    s = re.sub(r"\s*-\s*\d+\s*(?:ère|re|ème|e)\s+phase.*$", "", libelle, flags=re.I)
    s = re.sub(r"\s+Occitanie(\s+(Est|Ouest))?\s*$", "", s, flags=re.I)
    return s.strip().upper()


def nom_equipe(s):
    return re.sub(r"\s+\d+$", "", s.strip()).strip()  # retire le numéro d'équipe


def annee(saison, mois):
    a1 = int(saison.split("/")[0])
    return a1 if mois >= 7 else a1 + 1


def lire(texte, saison):
    comp, out = None, []
    for ln in texte.splitlines():
        m = ENTETE.match(ln)
        if m and "\t" not in ln.split(" - ")[0]:
            comp = competition_propre(m.group(2))
            continue
        m = LIGNE.match(ln)
        if not m:
            continue
        code, jj, mm, aa, heure, reste = m.groups()
        cols = [c for c in reste.split("\t")]
        equipes = [c for c in cols if c.strip()][:2]
        if len(equipes) < 2:
            continue
        dom, ext = nom_equipe(equipes[0]), nom_equipe(equipes[1])
        if not (CLUB.search(dom) or CLUB.search(ext)):
            continue
        y = int(aa) + (2000 if aa and len(aa) == 2 else 0) if aa else annee(saison, int(mm))
        domicile = bool(CLUB.search(dom))
        out.append(dict(
            code=code, competition=comp or code, date=f"{y:04d}-{int(mm):02d}-{int(jj):02d}",
            heure=heure.replace("h", ":").replace("H", ":"),
            adversaire=ext if domicile else dom, domicile=domicile))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fichier", help="texte copié de la page FFVB ('-' pour l'entrée standard)")
    ap.add_argument("--saison", default="2026/2027")
    ap.add_argument("--depuis", default=date.today().isoformat())
    ap.add_argument("--jusqu-a", dest="jusqua")
    ap.add_argument("--tous", action="store_true", help="garder aussi les matchs à l'extérieur")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    texte = sys.stdin.read() if a.fichier == "-" else open(a.fichier, encoding="utf-8").read()
    matchs = [m for m in lire(texte, a.saison)
              if (a.tous or m["domicile"]) and m["date"] >= a.depuis and (not a.jusqua or m["date"] <= a.jusqua)]
    js = json.dumps(matchs, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(js)
    print(js)
    print(f"{len(matchs)} match(s) retenu(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
