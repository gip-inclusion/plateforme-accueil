/* Tabbed search in the hero (progressive enhancement).
   Each tab reveals its own set of fields; without JavaScript the first
   field group stays visible and the others remain hidden. */
(function () {
  "use strict";

  var bar = document.querySelector(".recherche__onglets");
  if (!bar) {
    return;
  }

  var tabs = Array.prototype.slice.call(bar.querySelectorAll(".recherche__onglet"));

  function activate(tab) {
    tabs.forEach(function (o) {
      var active = o === tab;
      o.classList.toggle("est-actif", active);
      o.setAttribute("aria-selected", active ? "true" : "false");
      var fields = document.getElementById(o.getAttribute("aria-controls"));
      if (fields) {
        fields.hidden = !active;
      }
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      activate(tab);
    });
  });

  activate(tabs[0]);
})();
