# Stories automatiques dans Google Drive

Chaîne complète, sans intervention :

1. **Chaque jour à 4h UTC** – action « Mise à jour des matchs du Crès » → `data/matchs.json`
2. **Juste après** – action « Stories live du week-end » → génère dans `stories/` une story PNG
   par match du Crès **à domicile** du prochain week-end (+ `stories/index.json`)
3. **Chaque jour vers 8h** – Google Apps Script → copie ces PNG dans Google Drive :
   `Stories live Le Crès / Week-end du AAAA-MM-JJ /`

## Installation

### A. Dans GitHub (dépôt matchs-lecres)
Ajouter à la racine du dépôt :
- le dossier `generateur/` (script Python, polices et logos de la charte)
- le fichier `.github/workflows/stories.yml` (« Add file » > « Create new file », taper ce chemin, coller le contenu)

Puis onglet **Actions** > « Stories live du week-end » > **Run workflow** pour tester :
un dossier `stories/` doit apparaître avec les PNG.

### B. Dans Google (compte qui possède le Drive)
1. Aller sur https://script.google.com > **Nouveau projet**, le nommer « Stories Le Crès ».
2. Remplacer le contenu de `Code.gs` par celui de `google-apps-script/Code.gs`, enregistrer.
3. En haut, choisir la fonction **installerDeclencheur** puis **Exécuter**.
4. Google demande des autorisations (Drive + accès à une URL externe) : **Autoriser**.
   Si un écran « Application non validée » s'affiche : « Paramètres avancés » > « Accéder à Stories Le Crès ».
5. Le dossier **Stories live Le Crès** apparaît dans ton Drive avec les stories du week-end.

Ensuite tout tourne seul. Partage le dossier « Stories live Le Crès » avec la personne qui publie :
elle retrouve les stories sur son téléphone dans l'appli Google Drive, et ajoute le sticker lien
du live dans la zone prévue.

## Ajouter un logo de club
Déposer le PNG dans `generateur/assets/logos/` et ajouter son entrée dans `generateur/assets/logos/clubs.json`.
