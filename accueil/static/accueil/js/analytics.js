/* Audience measurement for the sections of the landing page.

   One delegated listener turns any element carrying data-matomo-category and
   data-matomo-action into a Matomo event. Tagging lives in the templates, next
   to the markup it measures, so a new CMS item is measured without touching
   this file — and, since these are ordinary tracker commands, without touching
   the tag manager container either.
*/

const SELECTOR = "[data-matomo-category][data-matomo-action]";

const config = JSON.parse(
  document.getElementById("accueil-config").textContent,
);

const postMessageToTrustedParents = (message) => {
  for (const host of config["frame-ancestors"]) {
    try {
      new URL(host); // Ignores wildcards.
      window.parent.postMessage(message, host);
    } catch {
      console.error(
        "Cannot postMessage to trusted origin from the CSP frame-ancestor entry for",
        host,
      );
    }
  }
};

const track = (element) => {
  const { matomoCategory, matomoAction } = element.dataset;
  // The hero runs one of three searches from a single form: its name is the
  // choice made inside it.
  const chosen =
    element.matches("form") &&
    element.querySelector("[data-matomo-name]:checked");
  const name = (
    element.dataset.matomoName ||
    chosen?.dataset.matomoName ||
    ""
  ).trim();

  postMessageToTrustedParents({
    source: "plateforme-accueil",
    type: "analytics",
    matomoCategory,
    matomoAction,
    matomoName: name,
  });
};

// Clicks land on the icon or the label inside a link or a button, hence closest().
document.addEventListener("click", (event) => {
  const element = event.target.closest?.(SELECTOR);
  if (element && !element.matches("form, input")) {
    track(element);
  }
});

// A radio is also changed with the arrow keys, which fires no click at all.
document.addEventListener("change", (event) => {
  const element = event.target.closest?.(SELECTOR);
  if (element) {
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
