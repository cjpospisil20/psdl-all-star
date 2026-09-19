/* Progressive enhancement only.

   The site is static HTML and every page is complete and usable with JavaScript off -- all
   rows are present in the markup. This file adds two conveniences on top:

     1. the player search filters the leaderboard in place
     2. long leaderboards collapse to a preview until asked to expand

   Written against the markup build.py emits. No framework, no build step. */

(function () {
  "use strict";

  /* ---- 1. filter the leaderboard as you type ---------------------------- */

  var search = document.getElementById("find");
  if (search) {
    var list = document.querySelectorAll("[data-row]");
    var empty = document.getElementById("no-match");

    // Two indexes per row. League names are full of nicknames and apostrophes, and people
    // search for the name they know, not the one DartConnect stores:
    //   "cam green"  must find  Cam "Jiminy" Green      -> needs per-token matching
    //   "obrien"     must find  Kevin O'Brien           -> needs punctuation stripped, not spaced
    var strip = function (s) {
      return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
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
      // every word typed has to appear somewhere -- order and nicknames don't matter
      return tokens.every(function (t) {
        return loose.indexOf(t) !== -1 || solid.indexOf(t) !== -1;
      });
    };

    var filter = function () {
      var q = search.value;
      var shown = 0;
      Array.prototype.forEach.call(list, function (row) {
        var hit = matches(row.getAttribute("data-row"), q);
        row.hidden = !hit;
        if (hit) shown++;
      });
      // Searching should reach the whole division, not just the preview.
      if (spaced(q)) expand();
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
    // Only collapse once JS is confirmed running, so a no-JS visitor keeps the full table.
    Array.prototype.forEach.call(document.querySelectorAll("[data-extra]"), function (row) {
      row.hidden = true;
    });
    more.hidden = false;
    more.addEventListener("click", function (e) {
      e.preventDefault();
      expand();
    });
  }
})();
