/* City autocomplete for the searches (progressive enhancement), backed by our
   /api/cities proxy. Two consumers share one combobox core:
   - hero forms ([data-recherche-ville]): picking a city fills the hidden "city"
     slug and points the form at its results page;
   - "Je fais une recherche" sections ([data-recherche-section]): clicking a
     filter pill or card opens a modal asking for the city, then goes to the
     results filtered by both.
   Without JavaScript the forms and pill/card links still work (they land on the
   target search page with the filter preselected, where the city is entered). */
(function () {
  "use strict";

  var DELAY = 250;

  function debounce(fn, delay) {
    var t;
    return function () {
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(null, args);
      }, delay);
    };
  }

  // Wires an input + listbox against /api/cities. onPick({slug,label}) fires
  // on selection; onEdit() fires whenever the text changes (to drop a stale pick).
  function autocomplete(container, input, list, onPick, onEdit) {
    var options = [];
    var active = -1;
    var controller = null;

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
      options = [];
      active = -1;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    function highlight(i) {
      options.forEach(function (o, idx) {
        o.setAttribute("aria-selected", idx === i ? "true" : "false");
      });
      active = i;
      if (i >= 0) {
        input.setAttribute("aria-activedescendant", options[i].id);
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    }

    function pick(item) {
      onPick(item);
      closeList();
    }

    function showOptions(results) {
      list.innerHTML = "";
      options = results.map(function (item, i) {
        var li = document.createElement("li");
        li.className = "suggestions__item";
        li.id = list.id + "-opt-" + i;
        li.dataset.slug = item.slug;
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", "false");
        li.textContent = item.label;
        li.addEventListener("mousedown", function (e) {
          e.preventDefault();
          pick(item);
        });
        list.appendChild(li);
        return li;
      });
      if (options.length) {
        list.hidden = false;
        input.setAttribute("aria-expanded", "true");
      } else {
        closeList();
      }
    }

    var search = debounce(function (term) {
      if (controller) {
        controller.abort();
      }
      controller = new AbortController();
      fetch("/api/cities?q=" + encodeURIComponent(term), { signal: controller.signal })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          showOptions(data.results || []);
        })
        .catch(function () {
          /* aborted or failed: leave the list closed */
        });
    }, DELAY);

    input.addEventListener("input", function () {
      if (onEdit) {
        onEdit();
      }
      var term = input.value.trim();
      if (term.length < 1) {
        closeList();
        return;
      }
      search(term);
    });

    input.addEventListener("keydown", function (e) {
      if (list.hidden) {
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        highlight((active + 1) % options.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        highlight((active - 1 + options.length) % options.length);
      } else if (e.key === "Enter") {
        if (active >= 0) {
          e.preventDefault();
          pick({ label: options[active].textContent, slug: options[active].dataset.slug });
        }
      } else if (e.key === "Escape") {
        closeList();
      }
    });

    document.addEventListener("click", function (e) {
      if (!container.contains(e.target)) {
        closeList();
      }
    });
  }

  function wireForm(form) {
    var input = form.querySelector("[data-ville-saisie]");
    var slug = form.querySelector("[data-ville-slug]");
    var list = form.querySelector(".suggestions");
    if (!input || !slug || !list) {
      return;
    }
    var searchAction = form.getAttribute("action");
    var resultsAction = form.getAttribute("data-resultats");
    autocomplete(
      form,
      input,
      list,
      function (item) {
        input.value = item.label;
        slug.value = item.slug;
        form.setAttribute("action", resultsAction);
      },
      function () {
        slug.value = "";
        form.setAttribute("action", searchAction);
      }
    );
  }

  // The shared "which city?" modal. Returns { open(href, label) } or null.
  function initModal() {
    var modal = document.getElementById("modale-ville");
    if (!modal || typeof modal.showModal !== "function") {
      return null;
    }
    var form = modal.querySelector("[data-modale-form]");
    var input = modal.querySelector("[data-ville-saisie]");
    var slug = modal.querySelector("[data-ville-slug]");
    var list = modal.querySelector(".suggestions");
    var context = modal.querySelector("[data-modale-contexte]");
    var targetHref = null;

    autocomplete(
      modal,
      input,
      list,
      function (item) {
        input.value = item.label;
        slug.value = item.slug;
      },
      function () {
        slug.value = "";
      }
    );

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!slug.value) {
        input.focus();
        return;
      }
      var url = new URL(targetHref);
      url.searchParams.set("city", slug.value);
      window.top.location.href = url.toString();
    });

    modal.querySelector("[data-modale-fermer]").addEventListener("click", function () {
      modal.close();
    });
    // Click on the backdrop (the dialog element itself) closes the modal.
    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        modal.close();
      }
    });

    return {
      open: function (href, label) {
        targetHref = href;
        input.value = "";
        slug.value = "";
        if (context) {
          context.textContent = label || "";
        }
        modal.showModal();
        input.focus();
      },
    };
  }

  function wireSection(section, modal) {
    if (!modal) {
      return;
    }
    var links = section.querySelectorAll(".pastille-lien, .lien-fleche, .carte-media, .recherche-cta");
    Array.prototype.forEach.call(links, function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        var title = link.querySelector(".carte-media__titre");
        var label = (title ? title.textContent : link.textContent).trim().replace(/\s+/g, " ");
        modal.open(link.href, label);
      });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-recherche-ville]"), wireForm);
  var modal = initModal();
  Array.prototype.forEach.call(document.querySelectorAll("[data-recherche-section]"), function (section) {
    wireSection(section, modal);
  });
})();
