/* Enhances the thematic <select> into a custom dropdown that matches the city
   suggestions. The native <select> stays in the DOM (hidden) as the source of
   truth and the no-JS fallback, so the form submits the same "category" value. */
(function () {
  "use strict";

  var compteur = 0;

  function brancher(champ) {
    var select = champ.querySelector("select");
    if (!select) {
      return;
    }
    var options = Array.prototype.slice.call(select.options);
    var prefixe = "theme-" + compteur++;

    var valeur = document.createElement("span");
    valeur.className = "select-theme__valeur";

    var chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("class", "icone select-theme__chevron");
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = '<use href="#ri-arrow-down-s-line"/>';

    var declencheur = document.createElement("button");
    declencheur.type = "button";
    declencheur.className = "select-theme__declencheur";
    declencheur.setAttribute("role", "combobox");
    declencheur.setAttribute("aria-haspopup", "listbox");
    declencheur.setAttribute("aria-expanded", "false");
    declencheur.setAttribute("aria-label", select.getAttribute("aria-label") || "");
    declencheur.appendChild(valeur);
    declencheur.appendChild(chevron);

    var liste = document.createElement("ul");
    liste.className = "suggestions";
    liste.id = prefixe + "-liste";
    liste.setAttribute("role", "listbox");
    liste.hidden = true;

    var actif = -1;

    var elems = options.map(function (opt, i) {
      var li = document.createElement("li");
      li.className = "suggestions__item";
      li.id = prefixe + "-opt-" + i;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", opt.selected ? "true" : "false");
      li.textContent = opt.textContent;
      li.addEventListener("mousedown", function (e) {
        e.preventDefault();
        choisir(i);
      });
      liste.appendChild(li);
      return li;
    });

    function majValeur() {
      var opt = options[select.selectedIndex] || options[0];
      valeur.textContent = opt.textContent;
      valeur.classList.toggle("select-theme__valeur--vide", opt.value === "");
    }

    function surligner(i) {
      elems.forEach(function (e, idx) {
        e.setAttribute("aria-selected", idx === i ? "true" : "false");
      });
      actif = i;
      if (i >= 0) {
        declencheur.setAttribute("aria-activedescendant", elems[i].id);
        elems[i].scrollIntoView({ block: "nearest" });
      }
    }

    function ouvrir() {
      liste.hidden = false;
      declencheur.setAttribute("aria-expanded", "true");
      surligner(select.selectedIndex);
    }

    function fermer() {
      liste.hidden = true;
      declencheur.setAttribute("aria-expanded", "false");
      declencheur.removeAttribute("aria-activedescendant");
    }

    function choisir(i) {
      select.selectedIndex = i;
      majValeur();
      fermer();
      declencheur.focus();
    }

    declencheur.addEventListener("click", function () {
      if (liste.hidden) {
        ouvrir();
      } else {
        fermer();
      }
    });

    declencheur.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (liste.hidden) {
          ouvrir();
        } else {
          surligner((actif + (e.key === "ArrowDown" ? 1 : -1) + elems.length) % elems.length);
        }
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (liste.hidden) {
          ouvrir();
        } else if (actif >= 0) {
          choisir(actif);
        }
      } else if (e.key === "Escape") {
        fermer();
      }
    });

    document.addEventListener("click", function (e) {
      if (!champ.contains(e.target)) {
        fermer();
      }
    });

    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");
    champ.classList.add("select-theme--enrichi");
    champ.appendChild(declencheur);
    champ.appendChild(liste);
    majValeur();
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-select-theme]"), brancher);
})();
