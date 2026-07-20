/* Publishes the page height to the host site (iframe protocol, see README).
   Progressive enhancement: the page works fully without this script.

   The measured height is that of the real content (bottom edge of the lowest
   body child), not `scrollHeight`: in a self-sizing iframe, `scrollHeight`
   depends on the iframe height itself, which ratchets — the height grows but
   never shrinks back (think pages using `min-height: 100vh`).

   A ResizeObserver alone is not enough: if a page script rebuilds the DOM, the
   observed <body> is replaced and the observer goes silent. Hence also the
   window `resize` event (blind to node identity) and a MutationObserver that
   re-attaches the observation to the current <body>. */
(function () {
  "use strict";

  if (window.parent === window) {
    return; // not framed
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
    observateur.observe(document.documentElement); // iframe resizes
    observateur.observe(corpsObserve); // content changes
  }

  function hauteurContenu() {
    var bas = 0;
    var enfants = document.body.children;
    for (var i = 0; i < enfants.length; i++) {
      var element = enfants[i];
      var style = window.getComputedStyle(element);
      if (style.position === "fixed") {
        continue; // out of flow, tracks the viewport rather than the content
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
      return; // slack, so rounding does not ping-pong between host and iframe
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
