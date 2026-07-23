/* Tabbed search in the hero (progressive enhancement).
   Each tab reveals its own set of fields; without JavaScript the first
   field group stays visible and the others remain hidden. */
(function () {
  "use strict";

  var barre = document.querySelector(".recherche__onglets");
  if (!barre) {
    return;
  }

  var onglets = Array.prototype.slice.call(barre.querySelectorAll(".recherche__onglet"));

  function activer(onglet) {
    onglets.forEach(function (o) {
      var actif = o === onglet;
      o.classList.toggle("est-actif", actif);
      o.setAttribute("aria-selected", actif ? "true" : "false");
      var champs = document.getElementById(o.getAttribute("aria-controls"));
      if (champs) {
        champs.hidden = !actif;
      }
    });
  }

  onglets.forEach(function (onglet) {
    onglet.addEventListener("click", function () {
      activer(onglet);
    });
  });

  activer(onglets[0]);
})();
