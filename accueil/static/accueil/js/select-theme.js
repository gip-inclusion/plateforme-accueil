/* Enhances the thematic <select> into a custom dropdown that matches the city
   suggestions. The native <select> stays in the DOM (hidden) as the source of
   truth and the no-JS fallback, so the form submits the same "category" value. */
(function () {
  "use strict";

  var counter = 0;

  function wire(champ) {
    var select = champ.querySelector("select");
    if (!select) {
      return;
    }
    var options = Array.prototype.slice.call(select.options);
    var prefix = "theme-" + counter++;

    var value = document.createElement("span");
    value.className = "select-theme__valeur";

    var chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("class", "icone select-theme__chevron");
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = '<use href="#ri-arrow-down-s-line"/>';

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "select-theme__declencheur";
    trigger.setAttribute("role", "combobox");
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", select.getAttribute("aria-label") || "");
    trigger.appendChild(value);
    trigger.appendChild(chevron);

    var list = document.createElement("ul");
    list.className = "suggestions suggestions--theme";
    list.id = prefix + "-liste";
    list.setAttribute("role", "listbox");
    list.hidden = true;

    var active = -1;

    // The empty placeholder option stays in the <select> (it drives the button
    // label and the no-JS fallback) but is not shown as a row in the dropdown.
    // elems only holds the selectable rows; each keeps its <option> index.
    var elems = [];
    options.forEach(function (opt, i) {
      if (opt.value === "") {
        return;
      }
      var li = document.createElement("li");
      li.className = "suggestions__item";
      li.id = prefix + "-opt-" + i;
      li.dataset.index = i;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", opt.selected ? "true" : "false");
      if (opt.dataset.icon) {
        var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", "icone");
        svg.setAttribute("aria-hidden", "true");
        svg.innerHTML = '<use href="#' + opt.dataset.icon + '"/>';
        li.appendChild(svg);
      }
      li.appendChild(document.createTextNode(opt.textContent));
      // Select on click (mouseup), not mousedown, so the :active state shows
      // while the row is pressed before the dropdown closes.
      li.addEventListener("click", function () {
        pick(i);
      });
      list.appendChild(li);
      elems.push(li);
    });

    function updateValue() {
      var opt = options[select.selectedIndex] || options[0];
      value.textContent = opt.textContent;
      value.classList.toggle("select-theme__valeur--vide", opt.value === "");
    }

    function highlight(i) {
      elems.forEach(function (e, idx) {
        e.setAttribute("aria-selected", idx === i ? "true" : "false");
      });
      active = i;
      if (i >= 0) {
        trigger.setAttribute("aria-activedescendant", elems[i].id);
        elems[i].scrollIntoView({ block: "nearest" });
      }
    }

    // elems position of the currently selected option (-1 when the placeholder
    // is selected, so nothing is highlighted).
    function currentPosition() {
      for (var i = 0; i < elems.length; i++) {
        if (Number(elems[i].dataset.index) === select.selectedIndex) {
          return i;
        }
      }
      return -1;
    }

    function open() {
      list.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      highlight(currentPosition());
    }

    function closeList() {
      list.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      trigger.removeAttribute("aria-activedescendant");
    }

    function pick(i) {
      select.selectedIndex = i;
      updateValue();
      closeList();
      trigger.focus();
    }

    trigger.addEventListener("click", function () {
      if (list.hidden) {
        open();
      } else {
        closeList();
      }
    });

    trigger.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (list.hidden) {
          open();
        } else {
          highlight((active + (e.key === "ArrowDown" ? 1 : -1) + elems.length) % elems.length);
        }
      } else if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (list.hidden) {
          open();
        } else if (active >= 0) {
          pick(Number(elems[active].dataset.index));
        }
      } else if (e.key === "Escape") {
        closeList();
      }
    });

    document.addEventListener("click", function (e) {
      if (!champ.contains(e.target)) {
        closeList();
      }
    });

    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");
    champ.classList.add("select-theme--enrichi");
    champ.appendChild(trigger);
    champ.appendChild(list);
    updateValue();
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-select-theme]"), wire);
})();
