/* Progressive enhancement only.

   The site is static HTML and every page is complete and usable with JavaScript off -- all
   rows are present in the markup. This file adds conveniences on top:

     1. the player search filters the leaderboard in place
     2. long leaderboards collapse to a preview until asked to expand
     3. back links use history.back() when the referrer matches
     4. the week filter on match nights

   Written against the markup build.py emits. No framework, no build step. */

(function () {
  "use strict";

  /* ---- 1. filter the leaderboard as you type ---------------------------- */

  var search = document.getElementById("find");
  if (search) {
    var list = document.querySelectorAll("[data-row]");
    var empty = document.getElementById("no-match");

    var strip = function (s) {
      return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    };
    var spaced = function (s) {
      return strip(s).replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
    };
    var tight = function (s) {
      return strip(s).replace(/[^a-z0-9]/g, "");
    };

    var matches = function (haystack, query) {
      var loose = spaced(haystack), solid = tight(haystack);
      var tokens = spaced(query).split(" ").filter(Boolean);
      if (!tokens.length) return true;
      return tokens.every(function (t) {
        return loose.indexOf(t) !== -1 || solid.indexOf(t) !== -1;
      });
    };

    var filter = function () {
      var q = search.value;
      if (spaced(q)) expand();
      var shown = 0;
      Array.prototype.forEach.call(list, function (row) {
        var hit = matches(row.getAttribute("data-row"), q);
        row.hidden = !hit;
        if (hit) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    };

    search.addEventListener("input", filter);
    search.addEventListener("search", filter);
  }

  /* ---- 2. collapse long leaderboards ------------------------------------ */

  var more = document.getElementById("show-all");

  function expand() {
    if (!more || more.hidden) return;
    Array.prototype.forEach.call(document.querySelectorAll("[data-extra]"), function (row) {
      row.removeAttribute("data-extra");
      row.hidden = false;
    });
    more.hidden = true;
  }

  if (more) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-extra]"), function (row) {
      row.hidden = true;
    });
    more.hidden = false;
    more.addEventListener("click", function (e) {
      e.preventDefault();
      expand();
    });
  }

  /* ---- 3. back links: history.back() when the referrer matches ---------- */

  var back = document.querySelector("a.back[data-back]");
  if (back) {
    back.addEventListener("click", function (e) {
      var pages = (back.getAttribute("data-back") || "").split(" ");
      var root = new URL(".", back.href).href;
      try {
        var ref = document.referrer;
        var fromList = pages.some(function (p) { return ref === root + p; });
        if (fromList && history.length > 1) {
          e.preventDefault();
          history.back();
        }
      } catch (_) { /* cross-origin referrer -- fall through to the plain link */ }
    });
  }

  /* ---- 4. week filter on match nights ----------------------------------- */

  var weekSelect = document.getElementById("week");
  if (weekSelect) {
    var filterWrap = weekSelect.closest(".filter");
    if (filterWrap) filterWrap.hidden = false;

    var matchRows = document.querySelectorAll("[data-week]");
    var noWeek = document.getElementById("no-week");
    var countEl = document.getElementById("match-count");
    var divLinks = document.querySelectorAll(".divnav a");

    var applyWeek = function () {
      var w = weekSelect.value;
      var shown = 0;
      Array.prototype.forEach.call(matchRows, function (row) {
        var visible = !w || row.getAttribute("data-week") === w;
        row.hidden = !visible;
        if (visible) shown++;
      });
      if (noWeek) noWeek.hidden = shown !== 0;
      if (countEl) countEl.textContent = shown;

      var hash = w ? "#week-" + w : "";
      if (history.replaceState) history.replaceState(null, "", location.pathname + hash);
      Array.prototype.forEach.call(divLinks, function (a) {
        var base = a.href.split("#")[0];
        a.href = base + hash;
      });
    };

    var hash = location.hash.match(/^#week-(\d+)$/);
    if (hash) {
      weekSelect.value = hash[1];
      if (weekSelect.value !== hash[1]) weekSelect.value = "";
    }

    weekSelect.addEventListener("change", applyWeek);
    applyWeek();
  }
})();
