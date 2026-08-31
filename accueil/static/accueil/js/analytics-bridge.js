/* Adopts the host's consent and identity before letting the tracker run.

   This page has no consent banner of its own, and no business counting a
   visitor of its own: the person is already on a visit at the host, and our
   hits belong to that visit, in the host's Matomo site. Both facts arrive
   together over the iframe protocol (see README).

   Order matters, and is the whole point of this file: the tracker serialises
   its request as soon as the tag fires, so the identity has to be in place
   first. Hence the container's Matomo tag firing on the event pushed below
   rather than on page view. */

/* Defence in depth only: `frame-ancestors` already decides who may embed us,
   and the message must come from that embedder. localhost is in the list
   because the CSP admits it in DEBUG. */
const HOST_ORIGIN =
  /^https:\/\/([a-z0-9-]+\.)*(inclusion\.gouv\.fr|inclusion\.beta\.gouv\.fr|cleverapps\.io|scalingo\.io)$|^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;

// Matomo's own shape for a visitor id. A malformed one is dropped rather than
// passed on, where it would fail deep inside the tracker with no signal.
const VISITOR_ID = /^[0-9a-f]{16}$/;

window._paq = window._paq || [];
window._mtm = window._mtm || [];

// The host republishes on every message we send it, so the same grant arrives
// many times: `consented` makes a repeat a no-op, and `started` keeps the tag
// to one firing per page, so a withdrawal followed by a new grant does not
// count a second page view.
let consented = false;
let started = false;

window.addEventListener("message", (event) => {
  if (event.source !== window.parent || !HOST_ORIGIN.test(event.origin)) {
    return;
  }
  const data = event.data;
  if (!data || data.source !== "plateforme-accueil" || data.type !== "analytics") {
    return;
  }

  // Withdrawal has to be honoured for as long as the page is open: an iframe
  // outlives the click that revokes consent on the host, so treating the first
  // grant as final would keep measuring someone who asked us to stop.
  if (data.consent !== true) {
    if (consented) {
      consented = false;
      window._paq.push(["forgetConsentGiven"]);
    }
    return;
  }

  if (consented) {
    return;
  }
  consented = true;

  // Queued on `_paq` while no tracker exists yet; replayed in order the moment
  // the container creates one, which the event below is what triggers.
  if (VISITOR_ID.test(data.visitorId)) {
    window._paq.push(["setVisitorId", data.visitorId]);
  }
  window._paq.push(["setConsentGiven"]);

  if (!started) {
    started = true;
    // `hostSiteId` feeds the container's Matomo configuration, so each
    // environment measures into the site its host measures into — and a review
    // app, which never sends this message, measures nowhere.
    window._mtm.push({ event: "host-analytics", hostSiteId: data.siteId });
  }
});
