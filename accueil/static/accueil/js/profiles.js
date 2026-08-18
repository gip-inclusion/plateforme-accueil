/* Tabs for the "Pour qui ?" section (progressive enhancement).
   Without JavaScript the tab bar stays hidden and the four profiles are
   stacked; with it, the bar is revealed and one panel shows at a time. */

const bar = document.querySelector(".profils__onglets");

if (bar) {
  const tabs = [...bar.querySelectorAll(".profils__onglet")];

  const activate = (chosen) => {
    for (const tab of tabs) {
      const active = tab === chosen;
      tab.classList.toggle("est-actif", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
      const panel = document.getElementById(tab.getAttribute("aria-controls"));
      if (panel) {
        panel.hidden = !active;
      }
    }
  };

  for (const tab of tabs) {
    tab.addEventListener("click", () => activate(tab));
  }

  bar.hidden = false;
  activate(tabs[0]);
}
