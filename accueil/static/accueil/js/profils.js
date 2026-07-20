/* Tabs for the "Pour qui ?" section (progressive enhancement).
   Without JavaScript the tab bar stays hidden and the four profiles are
   stacked; with it, the bar is revealed and one panel shows at a time. */
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
