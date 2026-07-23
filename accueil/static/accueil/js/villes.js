/* City autocomplete for the searches (progressive enhancement), backed by our
   /api/villes proxy. Two consumers share one combobox core:
   - hero forms ([data-recherche-ville]): picking a city fills the hidden "city"
     slug and points the form at its results page;
   - "Je fais une recherche" sections ([data-recherche-section]): clicking a
     filter pill or card opens a modal asking for the city, then goes to the
     results filtered by both.
   Without JavaScript the forms and pill/card links still work (they land on the
   target search page with the filter preselected, where the city is entered). */
(function () {
  "use strict";

  var DELAI = 250;

  function debounce(fn, delai) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(null, args);
      }, delai);
    };
  }

  // Wires an input + listbox against /api/villes. onChoisir({slug,label}) fires
  // on selection; onEdit() fires whenever the text changes (to drop a stale pick).
  function autocomplete(conteneur, saisie, liste, onChoisir, onEdit) {
    var options = [];
    var actif = -1;
    var controleur = null;

    function fermer() {
      liste.hidden = true;
      liste.innerHTML = "";
      options = [];
      actif = -1;
      saisie.setAttribute("aria-expanded", "false");
      saisie.removeAttribute("aria-activedescendant");
    }

    function surligner(i) {
      options.forEach(function (o, idx) {
        o.setAttribute("aria-selected", idx === i ? "true" : "false");
      });
      actif = i;
      if (i >= 0) {
        saisie.setAttribute("aria-activedescendant", options[i].id);
      } else {
        saisie.removeAttribute("aria-activedescendant");
      }
    }

    function choisir(item) {
      onChoisir(item);
      fermer();
    }

    function afficher(resultats) {
      liste.innerHTML = "";
      options = resultats.map(function (item, i) {
        var li = document.createElement("li");
        li.className = "suggestions__item";
        li.id = liste.id + "-opt-" + i;
        li.dataset.slug = item.slug;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = item.label;
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          choisir(item);
        });
        liste.appendChild(li);
        return li;
      });
      if (options.length) {
        liste.hidden = false;
        saisie.setAttribute("aria-expanded", "true");
      } else {
        fermer();
      }
    }

    var chercher = debounce(function (terme) {
      if (controleur) {
        controleur.abort();
      }
      controleur = new AbortController();
      fetch("/api/villes?q=" + encodeURIComponent(terme), { signal: controleur.signal })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          afficher(data.resultats || []);
        })
        .catch(function () {
          /* aborted or failed: leave the list closed */
        });
    }, DELAI);

    saisie.addEventListener("input", function () {
      if (onEdit) {
        onEdit();
      }
      var terme = saisie.value.trim();
      if (terme.length < 1) {
        fermer();
        return;
      }
      chercher(terme);
    });

    saisie.addEventListener("keydown", function (e) {
      if (liste.hidden) {
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        surligner((actif + 1) % options.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        surligner((actif - 1 + options.length) % options.length);
      } else if (e.key === "Enter") {
        if (actif >= 0) {
          e.preventDefault();
          choisir({ label: options[actif].textContent, slug: options[actif].dataset.slug });
        }
      } else if (e.key === "Escape") {
        fermer();
      }
    });

    document.addEventListener("click", function (e) {
      if (!conteneur.contains(e.target)) {
        fermer();
      }
    });
  }

  function brancherForm(form) {
    var saisie = form.querySelector("[data-ville-saisie]");
    var slug = form.querySelector("[data-ville-slug]");
    var liste = form.querySelector(".suggestions");
    if (!saisie || !slug || !liste) {
      return;
    }
    var actionRecherche = form.getAttribute("action");
    var actionResultats = form.getAttribute("data-resultats");
    autocomplete(
      form,
      saisie,
      liste,
      function (item) {
        saisie.value = item.label;
        slug.value = item.slug;
        form.setAttribute("action", actionResultats);
      },
      function () {
        slug.value = "";
        form.setAttribute("action", actionRecherche);
      }
    );
  }

  // The shared "which city?" modal. Returns { ouvrir(href, label) } or null.
  function initModale() {
    var modale = document.getElementById("modale-ville");
    if (!modale || typeof modale.showModal !== "function") {
      return null;
    }
    var form = modale.querySelector("[data-modale-form]");
    var saisie = modale.querySelector("[data-ville-saisie]");
    var slug = modale.querySelector("[data-ville-slug]");
    var liste = modale.querySelector(".suggestions");
    var contexte = modale.querySelector("[data-modale-contexte]");
    var cibleHref = null;

    autocomplete(
      modale,
      saisie,
      liste,
      function (item) {
        saisie.value = item.label;
        slug.value = item.slug;
      },
      function () {
        slug.value = "";
      }
    );

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!slug.value) {
        saisie.focus();
        return;
      }
      var url = new URL(cibleHref);
      url.searchParams.set("city", slug.value);
      window.top.location.href = url.toString();
    });

    modale.querySelector("[data-modale-fermer]").addEventListener("click", function () {
      modale.close();
    });
    // Click on the backdrop (the dialog element itself) closes the modal.
    modale.addEventListener("click", function (e) {
      if (e.target === modale) {
        modale.close();
      }
    });

    return {
      ouvrir: function (href, label) {
        cibleHref = href;
        saisie.value = "";
        slug.value = "";
        if (contexte) {
          contexte.textContent = label || "";
        }
        modale.showModal();
        saisie.focus();
      },
    };
  }

  function brancherSection(section, modale) {
    if (!modale) {
      return;
    }
    var liens = section.querySelectorAll(".pastille-lien, .lien-fleche, .carte-media");
    Array.prototype.forEach.call(liens, function (lien) {
      lien.addEventListener("click", function (e) {
        e.preventDefault();
        var titre = lien.querySelector(".carte-media__titre");
        var label = (titre ? titre.textContent : lien.textContent).trim().replace(/\s+/g, " ");
        modale.ouvrir(lien.href, label);
      });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-recherche-ville]"), brancherForm);
  var modale = initModale();
  Array.prototype.forEach.call(document.querySelectorAll("[data-recherche-section]"), function (section) {
    brancherSection(section, modale);
  });
})();
