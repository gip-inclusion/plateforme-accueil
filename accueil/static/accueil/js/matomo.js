/* Matomo Tag Manager container bootstrap.
 *
 * Vendor snippet, moved out of the page because inline <script> is banned
 * (see CLAUDE.md). Loaded from base.html so every page is measured.
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
