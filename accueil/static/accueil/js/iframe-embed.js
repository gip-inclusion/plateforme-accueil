/* Host-side script for the Plateforme de l'inclusion iframe.
   Usage on the embedding site:
     <iframe src="…" data-plateforme-accueil …></iframe>
     <script src="…/static/accueil/js/iframe-embed.js" defer></script>
   Listens for { source: "plateforme-accueil", type: "resize", height } messages
   and resizes the matching iframe. Without it the iframe simply keeps its
   default height. */
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
