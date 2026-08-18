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

if (window.parent !== window) {
  let lastHeight = 0;
  let scheduledMeasure = null;
  let observedBody = null;

  const observer = "ResizeObserver" in window ? new ResizeObserver(() => scheduleMeasure()) : null;

  const attachObserver = () => {
    if (observer === null || document.body === observedBody) {
      return;
    }
    observedBody = document.body;
    observer.disconnect();
    observer.observe(document.documentElement); // iframe resizes
    observer.observe(observedBody); // content changes
  };

  const contentHeight = () => {
    let bottom = 0;
    for (const element of document.body.children) {
      const style = window.getComputedStyle(element);
      if (style.position === "fixed") {
        continue; // out of flow, tracks the viewport rather than the content
      }
      const bottomMargin = parseFloat(style.marginBottom) || 0;
      bottom = Math.max(bottom, element.getBoundingClientRect().bottom + bottomMargin);
    }
    return Math.ceil(bottom + window.scrollY);
  };

  const publishHeight = () => {
    scheduledMeasure = null;
    attachObserver();
    const height = contentHeight();
    if (Math.abs(height - lastHeight) < 2) {
      return; // slack, so rounding does not ping-pong between host and iframe
    }
    lastHeight = height;
    window.parent.postMessage({ source: "plateforme-accueil", type: "resize", height }, "*");
  };

  const scheduleMeasure = () => {
    if (scheduledMeasure === null) {
      scheduledMeasure = window.requestAnimationFrame(publishHeight);
    }
  };

  attachObserver();
  window.addEventListener("load", scheduleMeasure);
  window.addEventListener("resize", scheduleMeasure);
  new MutationObserver(scheduleMeasure).observe(document, { childList: true, subtree: true });
}
