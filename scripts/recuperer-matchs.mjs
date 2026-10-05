#!/usr/bin/env node
// Récupère les matchs du Crès Volley-Ball sur le site FFVB (ffvbbeach.org) pour chaque
// poule listée dans config/poules.json, et écrit data/matchs.json.
// Node 20+ (fetch natif), aucune dépendance.
//
//   node scripts/recuperer-matchs.mjs              -> écrit data/matchs.json
//   node scripts/recuperer-matchs.mjs --html f.html --poule PMA   -> test sur un fichier local

import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = "https://www.ffvbbeach.org/ffvbapp/resu/vbspo_calendrier.php";

// ---------- utilitaires ----------
const ENTITES = { nbsp: " ", amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", eacute: "é", egrave: "è",
  ecirc: "ê", agrave: "à", ccedil: "ç", ocirc: "ô", icirc: "î", ucirc: "û", Eacute: "É", Egrave: "È" };

function texte(html) {
  return html
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&([a-z]+);/gi, (m, e) => ENTITES[e] ?? m)
    .replace(/\s+/g, " ")
    .trim();
}

function sansAccents(s) {
  return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
}

function annee(saison, mois) {
  const a1 = parseInt(saison.split("/")[0], 10);
  return mois >= 7 ? a1 : a1 + 1;
}

async function telecharger(url) {
  const rep = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0 (lecres-vb-matchs)" } });
  if (!rep.ok) throw new Error(`HTTP ${rep.status} sur ${url}`);
  const buf = Buffer.from(await rep.arrayBuffer());
  // Le site FFVB est souvent en ISO-8859-1 : on lit le charset annoncé.
  const ct = rep.headers.get("content-type") || "";
  let charset = (ct.match(/charset=([\w-]+)/i) || [])[1];
  if (!charset) {
    const head = buf.subarray(0, 2048).toString("latin1");
    charset = (head.match(/charset=["']?([\w-]+)/i) || [])[1] || "utf-8";
  }
  return new TextDecoder(charset.toLowerCase().replace("iso-8859-1", "latin1")).decode(buf);
}

// ---------- analyse d'une page calendrier ----------
// Chaque ligne de match : ... | CODE (PMA007) | JJ/MM | HH:MM | ÉQUIPE DOM | (vide) | ÉQUIPE EXT | sets | sets | détail | points | arbitres | ...
export function analyserPage(html, { saison, club, competition, poule }) {
  const reClub = new RegExp(`\\b${sansAccents(club).replace(/\s+/g, "\\s+")}\\b`);
  const matchs = [];
  for (const tr of html.match(/<tr[\s\S]*?<\/tr>/gi) || []) {
    const cells = (tr.match(/<t[dh][\s\S]*?<\/t[dh]>/gi) || []).map(texte);
    const iCode = cells.findIndex((c) => /^[A-Z0-9]{2,4}\d{3}$/.test(c));
    if (iCode < 0) continue;
    const date = cells[iCode + 1] || "";
    const heure = cells[iCode + 2] || "";
    const md = date.match(/^(\d{2})\/(\d{2})(?:\/(\d{2,4}))?$/);
    if (!md) continue;
    const apres = cells.slice(iCode + 3);
    const equipes = apres.filter((c) => c && !/^\d+$/.test(c)).slice(0, 2);
    if (equipes.length < 2) continue;
    const [dom, ext] = equipes.map((e) => e.replace(/\s+\d+$/, "").trim());
    const numDom = (equipes[0].match(/\s(\d+)$/) || [])[1];
    const numExt = (equipes[1].match(/\s(\d+)$/) || [])[1];
    const recoit = reClub.test(sansAccents(dom));
    if (!recoit && !reClub.test(sansAccents(ext))) continue;

    // Score : les deux premiers entiers isolés après la 2e équipe (sets gagnés)
    const iExt = apres.indexOf(equipes[1]);
    const nombres = apres.slice(iExt + 1).filter((c) => /^\d$/.test(c));
    const joue = nombres.length >= 2;
    const [, jj, mm, aa] = md;
    const y = aa ? (aa.length === 2 ? 2000 + +aa : +aa) : annee(saison, +mm);
    const hm = heure.match(/(\d{1,2})[:hH](\d{2})/);

    matchs.push({
      code: cells[iCode],
      poule,
      competition,
      date: `${y}-${mm}-${jj}`,
      heure: hm ? `${hm[1].padStart(2, "0")}:${hm[2]}` : heure,
      domicile: recoit,
      equipe_lecres: recoit ? numDom ?? null : numExt ?? null,
      adversaire: recoit ? ext : dom,
      joue,
      score: joue ? `${nombres[0]}-${nombres[1]}` : null,
    });
  }
  return matchs;
}

// ---------- programme principal ----------
async function main() {
  const conf = JSON.parse(await readFile(join(ROOT, "config", "poules.json"), "utf-8"));
  const args = process.argv.slice(2);

  if (args.includes("--html")) {  // mode test local
    const f = args[args.indexOf("--html") + 1];
    const code = args.includes("--poule") ? args[args.indexOf("--poule") + 1] : "TEST";
    const p = conf.poules.find((x) => x.code === code) || { code, competition: code };
    const res = analyserPage(await readFile(f, "latin1"), { ...conf, poule: p.code, competition: p.competition });
    console.log(JSON.stringify(res, null, 1));
    return;
  }

  const tous = [];
  const erreurs = [];
  for (const p of conf.poules) {
    const url = `${BASE}?saison=${encodeURIComponent(conf.saison).replace("%2F", "/")}&codent=${conf.codent}&poule=${p.code}`;
    try {
      const html = await telecharger(url);
      const m = analyserPage(html, { ...conf, poule: p.code, competition: p.competition });
      console.log(`${p.code} : ${m.length} match(s) du Crès`);
      if (m.length === 0) erreurs.push(`${p.code} : aucun match trouvé (structure de page changée ?)`);
      tous.push(...m);
    } catch (e) {
      console.error(`${p.code} : ${e.message}`);
      erreurs.push(`${p.code} : ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, 1500)); // politesse envers le serveur FFVB
  }

  tous.sort((a, b) => (a.date + a.heure).localeCompare(b.date + b.heure));
  const sortie = {
    club: "Le Crès Volley-Ball",
    saison: conf.saison,
    mis_a_jour: new Date().toISOString(),
    source: BASE,
    erreurs,
    matchs: tous,
  };
  await mkdir(join(ROOT, "data"), { recursive: true });
  await writeFile(join(ROOT, "data", "matchs.json"), JSON.stringify(sortie, null, 2) + "\n", "utf-8");
  console.log(`\n${tous.length} match(s) écrits dans data/matchs.json`);

  // Si TOUTES les poules ont échoué, on fait échouer l'action pour être prévenu.
  if (tous.length === 0) process.exit(1);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
