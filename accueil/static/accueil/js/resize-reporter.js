/* Publie la hauteur de la page au site hôte (protocole iframe, cf. README).
   Amélioration progressive : la page fonctionne intégralement sans ce script. */
(function () {
  "use strict";

  if (window.parent === window) {
    return; // pas dans une iframe
  }

  function publierHauteur() {
    window.parent.postMessage(
      {
        source: "plateforme-accueil",
        type: "resize",
        height: document.documentElement.scrollHeight,
      },
      "*"
    );
  }

  if ("ResizeObserver" in window) {
    new ResizeObserver(publierHauteur).observe(document.documentElement);
  }
  window.addEventListener("load", publierHauteur);
})();
