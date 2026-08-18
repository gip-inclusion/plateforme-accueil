/* Matomo Tag Manager container bootstrap.
 *
 * Vendor snippet, kept in its own file because the page carries no inline
 * script. Loaded from base.html so every page is measured, and deliberately
 * without defer: the container has to boot before the rest of the page.
 */

var _mtm = (window._mtm = window._mtm || []);
_mtm.push({ "mtm.startTime": new Date().getTime(), event: "mtm.Start" });

(function () {
  var d = document,
    g = d.createElement("script"),
    s = d.getElementsByTagName("script")[0];
  g.async = true;
  g.src = "https://matomo.inclusion.beta.gouv.fr/js/container_9eafCVJv.js";
  s.parentNode.insertBefore(g, s);
})();
