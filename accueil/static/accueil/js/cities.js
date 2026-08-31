/* City autocomplete for the searches (progressive enhancement), backed by our
   /api/cities proxy. Two consumers share one combobox core:
   - hero forms ([data-recherche-ville]): picking a city fills the hidden "city"
     slug and points the form at its results page;
   - "Je fais une recherche" sections ([data-recherche-section]): clicking a
     filter pill or card opens a modal asking for the city, then goes to the
     results filtered by both.
   Without JavaScript the forms and pill/card links still work (they land on the
   target search page with the filter preselected, where the city is entered). */

const DELAY = 250;

const debounce = (fn, delay) => {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};

// Wires an input + listbox against /api/cities. onPick({slug,label}) fires on
// selection; onEdit() fires whenever the text changes (to drop a stale pick).
const autocomplete = (container, input, list, onPick, onEdit) => {
  let options = [];
  let active = -1;
  let controller = null;

  const closeList = () => {
    list.hidden = true;
    list.replaceChildren();
    options = [];
    active = -1;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  };

  const highlight = (position) => {
    options.forEach((option, index) => {
      option.setAttribute("aria-selected", index === position ? "true" : "false");
    });
    active = position;
    if (position >= 0) {
      input.setAttribute("aria-activedescendant", options[position].id);
    } else {
      input.removeAttribute("aria-activedescendant");
    }
  };

  const pick = (item) => {
    onPick(item);
    closeList();
  };

  const showOptions = (results) => {
    list.replaceChildren();
    options = results.map((item, index) => {
      const row = document.createElement("li");
      row.className = "suggestions__item";
      row.id = `${list.id}-opt-${index}`;
      row.dataset.slug = item.slug;
      row.setAttribute("role", "option");
      row.setAttribute("aria-selected", "false");
      row.textContent = item.label;
      row.addEventListener("mousedown", (event) => {
        event.preventDefault();
        pick(item);
      });
      list.append(row);
      return row;
    });
    if (options.length) {
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    } else {
      closeList();
    }
  };

  const search = debounce(async (term) => {
    controller?.abort();
    controller = new AbortController();
    try {
      const response = await fetch(`/api/cities?q=${encodeURIComponent(term)}`, { signal: controller.signal });
      const data = await response.json();
      showOptions(data.results || []);
    } catch {
      /* aborted or failed: leave the list closed */
    }
  }, DELAY);

  input.addEventListener("input", () => {
    onEdit?.();
    const term = input.value.trim();
    if (term.length < 1) {
      closeList();
      return;
    }
    search(term);
  });

  input.addEventListener("keydown", (event) => {
    if (list.hidden) {
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      highlight((active + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      highlight((active - 1 + options.length) % options.length);
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      pick({ label: options[active].textContent, slug: options[active].dataset.slug });
    } else if (event.key === "Escape") {
      closeList();
    }
  });

  document.addEventListener("click", (event) => {
    if (!container.contains(event.target)) {
      closeList();
    }
  });
};

const wireForm = (form) => {
  const input = form.querySelector("[data-ville-saisie]");
  const slug = form.querySelector("[data-ville-slug]");
  const list = form.querySelector(".suggestions");
  if (!input || !slug || !list) {
    return;
  }
  // Where the search lands is the server's call (accueil.views.search):
  // picking a city here only has to fill the field.
  autocomplete(
    form,
    input,
    list,
    (item) => {
      input.value = item.label;
      slug.value = item.slug;
    },
    () => {
      slug.value = "";
    },
  );
};

// The shared "which city?" modal. Returns { open(href, label) } or null.
const initModal = () => {
  const modal = document.getElementById("modale-ville");
  if (!modal || typeof modal.showModal !== "function") {
    return null;
  }
  const form = modal.querySelector("[data-modale-form]");
  const input = modal.querySelector("[data-ville-saisie]");
  const slug = modal.querySelector("[data-ville-slug]");
  const list = modal.querySelector(".suggestions");
  const context = modal.querySelector("[data-modale-contexte]");
  let targetHref = null;

  autocomplete(
    modal,
    input,
    list,
    (item) => {
      input.value = item.label;
      slug.value = item.slug;
    },
    () => {
      slug.value = "";
    },
  );

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!slug.value) {
      input.focus();
      return;
    }
    const url = new URL(targetHref);
    url.searchParams.set("city", slug.value);
    window.top.location.href = url.toString();
  });

  modal.querySelector("[data-modale-fermer]").addEventListener("click", () => modal.close());
  // Click on the backdrop (the dialog element itself) closes the modal.
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      modal.close();
    }
  });

  return {
    open(href, label) {
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
};

const wireSection = (section, modal) => {
  if (!modal) {
    return;
  }
  const links = section.querySelectorAll(".pastille-lien, .lien-fleche, .carte-media, .recherche-cta");
  for (const link of links) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const title = link.querySelector(".carte-media__titre");
      const label = (title ? title.textContent : link.textContent).trim().replace(/\s+/g, " ");
      modal.open(link.href, label);
    });
  }
};

for (const form of document.querySelectorAll("[data-recherche-ville]")) {
  wireForm(form);
}

const modal = initModal();
for (const section of document.querySelectorAll("[data-recherche-section]")) {
  wireSection(section, modal);
}
