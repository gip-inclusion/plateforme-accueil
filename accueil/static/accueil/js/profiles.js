/* Tabs for the "Pour qui ?" section (progressive enhancement).
   Without JavaScript the tab bar stays hidden and the four profiles are
   stacked; with it, the bar is revealed and one panel shows at a time. */
(function () {
  "use strict";

  var bar = document.querySelector(".profils__onglets");
  if (!bar) {
    return;
  }

  var tabs = Array.prototype.slice.call(bar.querySelectorAll(".profils__onglet"));

  function activate(tab) {
    tabs.forEach(function (o) {
      var active = o === tab;
      o.classList.toggle("est-actif", active);
      o.setAttribute("aria-selected", active ? "true" : "false");
      var panel = document.getElementById(o.getAttribute("aria-controls"));
      if (panel) {
        panel.hidden = !active;
      }
    });
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      activate(tab);
    });
  });

  bar.hidden = false;
  activate(tabs[0]);
})();
