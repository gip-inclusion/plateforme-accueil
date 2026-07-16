/* Publie la hauteur de la page au site hôte (protocole iframe, cf. README).
   Amélioration progressive : la page fonctionne intégralement sans ce script.

   La hauteur mesurée est celle du contenu réel (bord bas de l'enfant le plus
   bas du body), pas `scrollHeight` : dans une iframe auto-dimensionnée,
   `scrollHeight` dépend de la hauteur de l'iframe elle-même (effet cliquet —
   la hauteur monte mais ne redescend jamais, cf. pages en `min-height: 100vh`).

   Les observations ne se limitent pas à un ResizeObserver : si un script de la
   page reconstruit le DOM (le <body> observé est alors remplacé), l'observateur
   devient muet. D'où, en plus : l'événement `resize` de window (insensible à
   l'identité des nœuds) et un MutationObserver qui ré-arrime l'observation au
   <body> courant. */
(function () {
  "use strict";

  if (window.parent === window) {
    return; // pas dans une iframe
  }

  var derniereHauteur = 0;
  var mesurePlanifiee = null;
  var observateur = "ResizeObserver" in window ? new ResizeObserver(planifierMesure) : null;
  var corpsObserve = null;

  function arrimerObservateur() {
    if (observateur === null || document.body === corpsObserve) {
      return;
    }
    corpsObserve = document.body;
    observateur.disconnect();
    observateur.observe(document.documentElement); // redimensionnements de l'iframe
    observateur.observe(corpsObserve); // changements du contenu
  }

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
    arrimerObservateur();
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

  arrimerObservateur();
  window.addEventListener("load", planifierMesure);
  window.addEventListener("resize", planifierMesure);
  new MutationObserver(planifierMesure).observe(document, { childList: true, subtree: true });
})();
