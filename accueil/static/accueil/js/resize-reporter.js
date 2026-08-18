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

  var lastHeight = 0;
  var scheduledMeasure = null;
  var observer = "ResizeObserver" in window ? new ResizeObserver(scheduleMeasure) : null;
  var observedBody = null;

  function attachObserver() {
    if (observer === null || document.body === observedBody) {
      return;
    }
    observedBody = document.body;
    observer.disconnect();
    observer.observe(document.documentElement); // iframe resizes
    observer.observe(observedBody); // content changes
  }

  function contentHeight() {
    var bottom = 0;
    var children = document.body.children;
    for (var i = 0; i < children.length; i++) {
      var element = children[i];
      var style = window.getComputedStyle(element);
      if (style.position === "fixed") {
        continue; // out of flow, tracks the viewport rather than the content
      }
      var rect = element.getBoundingClientRect();
      var bottomMargin = parseFloat(style.marginBottom) || 0;
      bottom = Math.max(bottom, rect.bottom + bottomMargin);
    }
    return Math.ceil(bottom + window.scrollY);
  }

  function publishHeight() {
    scheduledMeasure = null;
    attachObserver();
    var height = contentHeight();
    if (Math.abs(height - lastHeight) < 2) {
      return; // slack, so rounding does not ping-pong between host and iframe
    }
    lastHeight = height;
    window.parent.postMessage(
      {
        source: "plateforme-accueil",
        type: "resize",
        height: height,
      },
      "*"
    );
  }

  function scheduleMeasure() {
    if (scheduledMeasure === null) {
      scheduledMeasure = window.requestAnimationFrame(publishHeight);
    }
  }

  attachObserver();
  window.addEventListener("load", scheduleMeasure);
  window.addEventListener("resize", scheduleMeasure);
  new MutationObserver(scheduleMeasure).observe(document, { childList: true, subtree: true });
})();
