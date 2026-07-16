/* Onglets de la section « Pour qui ? » (amélioration progressive).
   Sans JavaScript : la barre d'onglets reste masquée (attribut hidden) et les
   quatre profils s'affichent à la suite. Avec JavaScript : la barre est
   révélée et un seul panneau est visible à la fois. */
(function () {
  "use strict";

  var barre = document.querySelector(".profils__onglets");
  if (!barre) {
    return;
  }

  var onglets = Array.prototype.slice.call(barre.querySelectorAll(".profils__onglet"));

  function activer(onglet) {
    onglets.forEach(function (o) {
      var actif = o === onglet;
      o.classList.toggle("est-actif", actif);
      o.setAttribute("aria-selected", actif ? "true" : "false");
      var panneau = document.getElementById(o.getAttribute("aria-controls"));
      if (panneau) {
        panneau.hidden = !actif;
      }
    });
  }

  onglets.forEach(function (onglet) {
    onglet.addEventListener("click", function () {
      activer(onglet);
    });
  });

  barre.hidden = false;
  activer(onglets[0]);
})();
