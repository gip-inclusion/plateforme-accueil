/* Script hôte pour l'iframe de La plateforme de l'inclusion.
   Usage côté site hôte :
     <iframe src="…" data-plateforme-accueil …></iframe>
     <script src="…/static/accueil/js/iframe-embed.js" defer></script>
   Écoute les messages { source: "plateforme-accueil", type: "resize", height }
   et ajuste la hauteur de l'iframe correspondante. Sans ce script, l'iframe
   garde simplement sa hauteur par défaut. */
(function () {
  "use strict";

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || data.source !== "plateforme-accueil" || data.type !== "resize") {
      return;
    }
    var frames = document.querySelectorAll("iframe[data-plateforme-accueil]");
    for (var i = 0; i < frames.length; i++) {
      if (frames[i].contentWindow === event.source) {
        frames[i].style.height = data.height + "px";
      }
    }
  });
})();
