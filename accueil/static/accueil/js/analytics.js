/* Audience measurement for the sections of the landing page.

   One delegated listener turns any element carrying data-matomo-category and
   data-matomo-action into a Matomo event. Tagging lives in the templates, next
   to the markup it measures, so a new CMS item is measured without touching
   this file — and, since these are ordinary tracker commands, without touching
   the tag manager container either.

   `_paq` is a queue the tracker replays once it exists, and it only exists
   after the host hands over its consent (see js/analytics-bridge.js), so
   nothing is sent before then. */

const SELECTOR = "[data-matomo-category][data-matomo-action]";

const track = (element) => {
  const { matomoCategory, matomoAction, matomoName } = element.dataset;
  const name = (matomoName || "").trim();
  window._paq = window._paq || [];
  window._paq.push(["trackEvent", matomoCategory, matomoAction, ...(name ? [name] : [])]);
};

// Clicks land on the icon or the label inside a link or a button, hence closest().
document.addEventListener("click", (event) => {
  const element = event.target.closest?.(SELECTOR);
  if (element && !element.matches("form")) {
    track(element);
  }
});

// Searches are measured when submitted, not when the button is pressed: the
// form can also be sent with the Enter key, and it can be cancelled by the
// browser's own validation.
document.addEventListener("submit", (event) => {
  const form = event.target.closest?.(SELECTOR);
  if (form) {
    track(form);
  }
});
