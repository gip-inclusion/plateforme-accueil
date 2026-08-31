/* Audience measurement for the sections of the landing page.

   One delegated listener turns any element carrying data-matomo-category and
   data-matomo-action into a data-layer event for the Matomo Tag Manager
   container booted in base.html (see js/matomo.js). Tagging lives in the
   templates, next to the markup it measures, so a new CMS item is measured
   without touching this file.

   The container has to map the "accueil.interaction" event onto a Matomo
   event tag; the variables are documented in the README. Nothing here depends
   on the tracker being loaded: pushes queue up in the array until it is. */

const EVENT = "accueil.interaction";
const SELECTOR = "[data-matomo-category][data-matomo-action]";

const track = (element) => {
  const { matomoCategory, matomoAction, matomoName } = element.dataset;
  window._mtm = window._mtm || [];
  window._mtm.push({
    event: EVENT,
    matomoCategory,
    matomoAction,
    matomoName: (matomoName || "").trim(),
  });
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
