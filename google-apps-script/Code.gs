/**
 * Copie automatiquement les stories « MATCH EN DIRECT » du Crès depuis GitHub
 * vers un dossier Google Drive, un sous-dossier par week-end.
 *
 * Installation : coller ce fichier dans un projet Apps Script (script.google.com),
 * exécuter une fois installerDeclencheur(), accepter les autorisations. C'est tout.
 */

const DEPOT = 'https://raw.githubusercontent.com/blecresvb/matchs-lecres/main/stories/';
const DOSSIER_RACINE = 'Stories live Le Crès';   // créé s'il n'existe pas

function synchroniserStories() {
  const index = JSON.parse(
    UrlFetchApp.fetch(DEPOT + 'index.json?t=' + Date.now(), { headers: { 'Cache-Control': 'no-cache' } })
      .getContentText());
  if (!index.fichiers || index.fichiers.length === 0) {
    console.log('Aucune story pour le week-end du ' + index.weekend);
    return;
  }

  const racine = dossier_(DriveApp.getRootFolder(), DOSSIER_RACINE);
  const semaine = dossier_(racine, 'Week-end du ' + index.weekend);

  index.fichiers.forEach(function (nom) {
    const blob = UrlFetchApp.fetch(DEPOT + encodeURIComponent(nom) + '?t=' + Date.now()).getBlob().setName(nom);
    const taille = blob.getBytes().length;
    // déjà là et identique -> rien à faire ; sinon remplacer (horaire modifié, etc.)
    const existants = semaine.getFilesByName(nom);
    let aJour = false;
    while (existants.hasNext()) {
      const f = existants.next();
      if (!aJour && f.getSize() === taille) { aJour = true; } else { f.setTrashed(true); }
    }
    if (aJour) return;
    semaine.createFile(blob);
    console.log('Copié : ' + nom);
  });
}

function dossier_(parent, nom) {
  const it = parent.getFoldersByName(nom);
  return it.hasNext() ? it.next() : parent.createFolder(nom);
}

/** À lancer une seule fois : synchronise maintenant puis chaque vendredi vers 9h. */
function installerDeclencheur() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'synchroniserStories') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('synchroniserStories').timeBased().onWeekDay(ScriptApp.WeekDay.FRIDAY).atHour(9).create();
  synchroniserStories();
}
