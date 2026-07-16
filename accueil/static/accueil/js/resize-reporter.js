/* Publie la hauteur de la page au site hôte (protocole iframe, cf. README).
   Amélioration progressive : la page fonctionne intégralement sans ce script.

   La hauteur mesurée est celle du contenu réel (bord bas de l'enfant le plus
   bas du body), pas `scrollHeight` : dans une iframe auto-dimensionnée,
   `scrollHeight` dépend de la hauteur de l'iframe elle-même (effet cliquet —
   la hauteur monte mais ne redescend jamais, cf. pages en `min-height: 100vh`). */
(function () {
  "use strict";

  if (window.parent === window) {
    return; // pas dans une iframe
  }

  var derniereHauteur = 0;
  var mesurePlanifiee = null;

  function hauteurContenu() {
    var bas = 0;
    var enfants = document.body.children;
    for (var i = 0; i < enfants.length; i++) {
      var element = enfants[i];
      var style = window.getComputedStyle(element);
      if (style.position === "fixed") {
        continue; // hors flux, suit le viewport et non le contenu
      }
      var rect = element.getBoundingClientRect();
      var margeBasse = parseFloat(style.marginBottom) || 0;
      bas = Math.max(bas, rect.bottom + margeBasse);
    }
    return Math.ceil(bas + window.scrollY);
  }

  function publierHauteur() {
    mesurePlanifiee = null;
    var hauteur = hauteurContenu();
    if (Math.abs(hauteur - derniereHauteur) < 2) {
      return; // tolérance : évite les boucles hôte <-> iframe sur arrondis
    }
    derniereHauteur = hauteur;
    window.parent.postMessage(
      {
        source: "plateforme-accueil",
        type: "resize",
        height: hauteur,
      },
      "*"
    );
  }

  function planifierMesure() {
    if (mesurePlanifiee === null) {
      mesurePlanifiee = window.requestAnimationFrame(publierHauteur);
    }
  }

  if ("ResizeObserver" in window) {
    var observateur = new ResizeObserver(planifierMesure);
    observateur.observe(document.documentElement); // redimensionnements de l'iframe
    observateur.observe(document.body); // changements du contenu
  }
  window.addEventListener("load", planifierMesure);
})();
