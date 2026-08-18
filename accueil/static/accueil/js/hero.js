/* Tabbed search in the hero (progressive enhancement).
   Each tab reveals its own set of fields; without JavaScript the first
   field group stays visible and the others remain hidden. */

const bar = document.querySelector(".recherche__onglets");

if (bar) {
  const tabs = [...bar.querySelectorAll(".recherche__onglet")];

  const activate = (chosen) => {
    for (const tab of tabs) {
      const active = tab === chosen;
      tab.classList.toggle("est-actif", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      const fields = document.getElementById(tab.getAttribute("aria-controls"));
      if (fields) {
        fields.hidden = !active;
      }
    }
  };

  for (const tab of tabs) {
    tab.addEventListener("click", () => activate(tab));
  }

  activate(tabs[0]);
}
