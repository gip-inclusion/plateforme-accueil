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
      // Top layer: never part of the content. An open <dialog> positioned
      // against the visible band would otherwise ratchet the height up.
      if (element.matches("dialog[open]")) {
        continue;
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

  /* The host's half of the protocol: it publishes the band of the iframe that
     is actually on screen, expressed in our own coordinate space. We expose it
     as CSS custom properties — enough for the city modal to sit in the visible
     band instead of the middle of a page taller than the window.

     Held while a dialog is open: a modal must not chase the scroll, which would
     lag a frame behind it across the process boundary. Being absolutely
     positioned, it simply scrolls away with the page, like any other content.
     The band is remembered rather than dropped, and applied on close: the host
     does not repeat a value it has already sent, so a message discarded here
     would leave the page stale until the next scroll — and place the next
     modal where the visitor was looking a while ago.

     Nothing here is required: a host that does not publish `viewport` leaves
     the custom properties unset, and the modal keeps its default centering. */
  let band = null;

  const applyBand = () => {
    if (band === null || document.querySelector("dialog[open]")) {
      return;
    }
    const root = document.documentElement;
    root.style.setProperty("--viewport-top", `${band.top}px`);
    root.style.setProperty("--viewport-height", `${band.height}px`);
    root.dataset.viewport = "";
  };

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (event.source !== window.parent || !data || data.source !== "plateforme-accueil") {
      return;
    }
    if (data.type !== "viewport" || !(data.height > 0)) {
      return;
    }
    band = { top: data.top, height: data.height };
    applyBand();
  });

  // `close` does not bubble, hence the capture phase.
  document.addEventListener("close", applyBand, true);

  attachObserver();
  window.addEventListener("load", scheduleMeasure);
  window.addEventListener("resize", scheduleMeasure);
  new MutationObserver(scheduleMeasure).observe(document, { childList: true, subtree: true });
}
