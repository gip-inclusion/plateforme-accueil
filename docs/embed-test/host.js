/* Instrumentation du banc d'essai — n'existe pas chez un vrai site hôte.
   Trois rôles :
   - journaliser les messages postés par la vitrine (protocole iframe) ;
   - afficher en continu la bande visible de l'iframe, calculée exactement
     comme le ferait un hôte qui publierait `viewport` : c'est la mesure
     qu'on veut valider avant de câbler quoi que ce soit ;
   - faire varier la largeur de l'iframe, la page devant rester lisible
     quelle que soit celle-ci. */
(function () {
  "use strict";

  var frame = document.querySelector("iframe[data-plateforme-accueil]");
  var cadre = document.querySelector("[data-cadre]");
  var sortieHauteur = document.querySelector("[data-sonde-hauteur]");
  var sortieBande = document.querySelector("[data-sonde-bande]");
  var sortieScroll = document.querySelector("[data-sonde-scroll]");
  var journal = document.querySelector("[data-sonde-journal]");

  var tracer = function (texte) {
    var ligne = document.createElement("li");
    ligne.textContent = texte;
    journal.prepend(ligne);
    while (journal.children.length > 40) {
      journal.lastElementChild.remove();
    }
  };

  // La bande de l'iframe réellement à l'écran, exprimée dans le repère du
  // document embarqué (l'iframe ne scrollant pas, il n'y a pas de second
  // système de coordonnées à réconcilier).
  var bandeVisible = function () {
    var rect = frame.getBoundingClientRect();
    var haut = Math.max(0, -rect.top);
    var hauteur = Math.min(rect.height, window.innerHeight - rect.top) - haut;
    return { top: Math.round(haut), height: Math.round(Math.max(0, hauteur)) };
  };

  var mesure = null;
  var rafraichir = function () {
    mesure = null;
    var bande = bandeVisible();
    sortieBande.textContent = bande.height > 0
      ? "top " + bande.top + " · h " + bande.height
      : "hors champ";
    sortieScroll.textContent = Math.round(window.scrollY) + " px";
  };

  var planifier = function () {
    if (mesure === null) {
      mesure = window.requestAnimationFrame(rafraichir);
    }
  };

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data || data.source !== "plateforme-accueil") {
      return;
    }
    if (data.type === "resize") {
      sortieHauteur.textContent = data.height + " px";
    }
    tracer("← " + data.type + " " + JSON.stringify(data).slice(0, 60));
    planifier();
  });

  for (var bouton of document.querySelectorAll("[data-largeur]")) {
    bouton.addEventListener("click", function (event) {
      cadre.style.width = event.currentTarget.dataset.largeur;
      planifier();
    });
  }

  window.addEventListener("scroll", planifier, { passive: true });
  window.addEventListener("resize", planifier);
  window.addEventListener("load", planifier);
  planifier();
})();
