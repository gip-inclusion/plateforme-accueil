/* Enhances the thematic <select> into a custom dropdown that matches the city
   suggestions. The native <select> stays in the DOM (hidden) as the source of
   truth and the no-JS fallback, so the form submits the same "category" value. */

const SVG_NS = "http://www.w3.org/2000/svg";

let counter = 0;

const icon = (name, className) => {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = `<use href="#${name}"/>`;
  return svg;
};

const wire = (field) => {
  const select = field.querySelector("select");
  if (!select) {
    return;
  }
  const options = [...select.options];
  const prefix = `theme-${counter++}`;

  const value = document.createElement("span");
  value.className = "select-theme__valeur";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "select-theme__declencheur";
  trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-label", select.getAttribute("aria-label") || "");
  trigger.append(value, icon("ri-arrow-down-s-line", "icone select-theme__chevron"));

  const list = document.createElement("ul");
  list.className = "suggestions suggestions--theme";
  list.id = `${prefix}-liste`;
  list.setAttribute("role", "listbox");
  list.hidden = true;

  let active = -1;

  // The empty placeholder option stays in the <select> (it drives the button
  // label and the no-JS fallback) but is not shown as a row in the dropdown.
  // `rows` only holds the selectable ones; each keeps its <option> index.
  const rows = [];
  options.forEach((option, index) => {
    if (option.value === "") {
      return;
    }
    const row = document.createElement("li");
    row.className = "suggestions__item";
    row.id = `${prefix}-opt-${index}`;
    row.dataset.index = index;
    row.setAttribute("role", "option");
    row.setAttribute("aria-selected", option.selected ? "true" : "false");
    if (option.dataset.icon) {
      row.append(icon(option.dataset.icon, "icone"));
    }
    row.append(option.textContent);
    // Select on click (mouseup), not mousedown, so the :active state shows
    // while the row is pressed before the dropdown closes.
    row.addEventListener("click", () => pick(index));
    list.append(row);
    rows.push(row);
  });

  const updateValue = () => {
    const option = options[select.selectedIndex] || options[0];
    value.textContent = option.textContent;
    value.classList.toggle("select-theme__valeur--vide", option.value === "");
  };

  const highlight = (position) => {
    rows.forEach((row, index) => {
      row.setAttribute("aria-selected", index === position ? "true" : "false");
    });
    active = position;
    if (position >= 0) {
      trigger.setAttribute("aria-activedescendant", rows[position].id);
      rows[position].scrollIntoView({ block: "nearest" });
    }
  };

  // Position in `rows` of the currently selected option (-1 when the
  // placeholder is selected, so nothing is highlighted).
  const currentPosition = () => rows.findIndex((row) => Number(row.dataset.index) === select.selectedIndex);

  const open = () => {
    list.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    highlight(currentPosition());
  };

  const closeList = () => {
    list.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    trigger.removeAttribute("aria-activedescendant");
  };

  const pick = (index) => {
    select.selectedIndex = index;
    updateValue();
    closeList();
    trigger.focus();
  };

  trigger.addEventListener("click", () => (list.hidden ? open() : closeList()));

  trigger.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (list.hidden) {
        open();
      } else {
        highlight((active + (event.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (list.hidden) {
        open();
      } else if (active >= 0) {
        pick(Number(rows[active].dataset.index));
      }
    } else if (event.key === "Escape") {
      closeList();
    }
  });

  document.addEventListener("click", (event) => {
    if (!field.contains(event.target)) {
      closeList();
    }
  });

  select.setAttribute("tabindex", "-1");
  select.setAttribute("aria-hidden", "true");
  field.classList.add("select-theme--enrichi");
  field.append(trigger, list);
  updateValue();
};

for (const field of document.querySelectorAll("[data-select-theme]")) {
  wire(field);
}
