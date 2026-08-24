/* Host-side script for the Plateforme de l'inclusion iframe.
   Usage on the embedding site:
     <iframe src="…" data-plateforme-accueil …></iframe>
     <script src="…/static/accueil/js/iframe-embed.js" defer></script>
   Two halves, both optional for the embedded page to work:
   - listens for { source: "plateforme-accueil", type: "resize", height }
     messages and resizes the matching iframe;
   - publishes back the band of each iframe that is actually on screen, so the
     page can place a modal where the visitor is looking. The iframe being as
     tall as its content, its own viewport covers the whole page: `position:
     fixed` inside it centres on the document, not on what is visible.
   Without this script the iframe simply keeps its default height, and the
   embedded page falls back to centring in its own viewport. */
(function () {
  "use strict";

  var frames = function () {
    return document.querySelectorAll("iframe[data-plateforme-accueil]");
  };

  /* The visible band of the iframe, expressed in the coordinate space of the
     embedded document. That document does not scroll (it is as tall as its
     content), so there is no second scroll offset to reconcile. */
  var publishViewport = function (frame) {
    if (!frame.contentWindow) {
      return;
    }
    var rect = frame.getBoundingClientRect();
    var top = Math.round(Math.max(0, -rect.top));
    var height = Math.round(Math.max(0, Math.min(rect.height, window.innerHeight - rect.top) - top));
    // Off screen, or unchanged since last time: nothing worth posting.
    if (height === 0 || (frame.plateformeBand === top + ":" + height)) {
      return;
    }
    frame.plateformeBand = top + ":" + height;
    frame.contentWindow.postMessage(
      { source: "plateforme-accueil", type: "viewport", top: top, height: height },
      new URL(frame.src, location.href).origin
    );
  };

  var scheduled = null;
  var publishAll = function () {
    scheduled = null;
    var list = frames();
    for (var i = 0; i < list.length; i++) {
      publishViewport(list[i]);
    }
  };

  var schedule = function () {
    if (scheduled === null) {
      scheduled = window.requestAnimationFrame(publishAll);
    }
  };

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || data.source !== "plateforme-accueil" || data.type !== "resize") {
      return;
    }
    var list = frames();
    for (var i = 0; i < list.length; i++) {
      if (list[i].contentWindow === event.source) {
        list[i].style.height = data.height + "px";
        // A taller iframe is a different band. This message also proves the
        // page is listening — our first `viewport` may have been posted before
        // it was — so forget the cached band to force the next one out.
        list[i].plateformeBand = null;
        schedule();
      }
    }
  });

  window.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule);
  window.addEventListener("load", schedule);
  schedule();
})();
