# Matchs du Crès Volley-Ball

Chaque jour, une GitHub Action lit le calendrier des poules du club sur le site FFVB
(ffvbbeach.org) et met à jour `data/matchs.json`. Ce fichier sert au skill Claude
« affiche-live-lecres » pour générer les stories « MATCH EN DIRECT » du week-end.

## Mise en place (une seule fois)

1. Sur github.com, créer un dépôt **public** nommé `matchs-lecres`
   (public pour que Claude puisse lire le JSON sans identifiant ; il ne contient que le calendrier public).
2. Y déposer le contenu de ce dossier : `.github/`, `config/`, `scripts/`, `README.md`
   (bouton « Add file » > « Upload files », glisser les dossiers).
3. Onglet **Actions** : activer les workflows si GitHub le demande, ouvrir
   « Mise à jour des matchs du Crès » puis cliquer **Run workflow** pour un premier lancement.
4. Vérifier que `data/matchs.json` est apparu dans le dépôt. Son adresse « Raw » ressemble à :
   `https://raw.githubusercontent.com/<compte>/matchs-lecres/main/data/matchs.json`
   — c'est elle qu'il faut donner à Claude.

Ensuite, l'action tourne seule tous les jours à 4h UTC et ne crée un commit que si un match change.

## Ajouter / changer une poule

Modifier `config/poules.json` : un objet par poule où joue une équipe du club
(`code` = valeur `poule=` dans l'URL FFVB, `competition` = nom en toutes lettres affiché sur la story).
Penser à changer `saison` en début de saison.

## Si l'action échoue ou trouve 0 match

Le site FFVB a peut-être changé la structure de sa page. Ouvrir la page calendrier d'une poule,
faire clic droit > « Enregistrer sous » (page HTML), et l'envoyer à Claude pour ajuster
`scripts/recuperer-matchs.mjs`. Test local : `node scripts/recuperer-matchs.mjs --html page.html --poule PMA`.

## Format de data/matchs.json

```json
{
  "mis_a_jour": "2026-10-05T04:00:12.000Z",
  "erreurs": [],
  "matchs": [
    { "code": "PMA012", "poule": "PMA", "competition": "PRÉNATIONALE MASCULINE",
      "date": "2026-10-17", "heure": "20:30", "domicile": true, "equipe_lecres": "1",
      "adversaire": "ASBAM MONTPELLIER", "joue": false, "score": null }
  ]
}
```
