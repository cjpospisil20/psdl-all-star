/* Progressive enhancement only.

   The site is static HTML and every page is complete and usable with JavaScript off -- all
   rows are present in the markup. This file adds conveniences on top:

     1. the player search filters the leaderboard in place
     2. long leaderboards collapse to a preview until asked to expand
     3. back links use history.back() when the referrer matches
     4. the schedule: division and team filters, and gilding tonight's matches while they're on

   Written against the markup build.py emits. No framework, no build step. */

(function () {
  "use strict";

  /* ---- shared: a forgiving text match ----------------------------------- */

  var strip = function (s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  };
  var spaced = function (s) {
    return strip(s).replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
  };
  var tight = function (s) {
    return strip(s).replace(/[^a-z0-9]/g, "");
  };

  // Every word of the query must appear, punctuation-blind: "smiths" finds "Smith's P.S.".
  var matches = function (haystack, query) {
    var loose = spaced(haystack), solid = tight(haystack);
    var tokens = spaced(query).split(" ").filter(Boolean);
    if (!tokens.length) return true;
    return tokens.every(function (t) {
      return loose.indexOf(t) !== -1 || solid.indexOf(t) !== -1;
    });
  };

  /* ---- 1. filter the leaderboard as you type ---------------------------- */

  var search = document.getElementById("find");
  if (search) {
    var list = document.querySelectorAll("[data-row]");
    var empty = document.getElementById("no-match");

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

  /* ---- 4. the schedule -------------------------------------------------- */

  // A static build cannot know what is on right now -- the site rebuilds on Wednesday mornings --
  // so "live" comes from the clock. Each night carries its first-darts moment with New York's
  // offset (data-start), so the sum is right whatever timezone the phone is set to. A night is
  // live from first darts until LIVE_MS later, then over. Nights are in date order, so tonight
  // is always the first one on the page: it only needs gilding, never moving.
  var division = document.getElementById("division");
  if (division) {
    var LIVE_MS = 4.5 * 60 * 60 * 1000;          // 7:30 PM first darts -> midnight
    var STORE = "psdl-schedule-division";
    var controls = document.querySelector(".sched-controls");
    var teamFind = document.getElementById("team-find");
    var nights = document.querySelectorAll(".night");
    var count = document.getElementById("fx-count");
    var noun = document.getElementById("fx-noun");
    var none = document.getElementById("no-fixtures");

    if (controls) controls.hidden = false;

    var choose = function (value) {
      division.value = value || "";
      if (division.value !== (value || "")) division.value = "";    // unknown -> All
    };

    // The division a link asked for wins; otherwise the one this phone picked last time.
    var asked = location.hash.match(/^#(division-\d+)$/);
    if (asked) {
      choose(asked[1]);
    } else {
      try { choose(localStorage.getItem(STORE)); } catch (_) { /* storage blocked */ }
    }

    var remember = function () {
      var hash = division.value ? "#" + division.value : "";
      try {
        history.replaceState(null, "", location.pathname + location.search + hash);
      } catch (_) { /* some frames refuse URL changes -- the filter still works */ }
      try {
        if (division.value) localStorage.setItem(STORE, division.value);
        else localStorage.removeItem(STORE);
      } catch (_) { /* storage blocked -- the hash still carries the choice */ }
    };

    var apply = function () {
      var now = Date.now();
      var want = division.value;
      var q = teamFind ? teamFind.value : "";
      var games = 0, rows = 0;
      Array.prototype.forEach.call(nights, function (night) {
        var start = Date.parse(night.getAttribute("data-start"));
        var over = now >= start + LIVE_MS;
        var live = !over && now >= start;
        night.classList.toggle("live", live);
        var tag = night.querySelector(".live-tag");
        if (tag) tag.hidden = !live;

        var visible = 0;
        Array.prototype.forEach.call(night.querySelectorAll(".fixture"), function (row) {
          var hit = !over &&
                    (!want || row.getAttribute("data-division") === want) &&
                    matches(row.getAttribute("data-row"), q);
          row.hidden = !hit;
          if (!hit) return;
          visible++;
          if (!row.classList.contains("bye")) games++;
        });
        night.hidden = visible === 0;
        rows += visible;
      });
      if (count) count.textContent = games;
      if (noun) noun.textContent = games === 1 ? "match" : "matches";
      if (none) none.hidden = rows !== 0;
    };

    division.addEventListener("change", function () { remember(); apply(); });
    if (teamFind) {
      teamFind.addEventListener("input", apply);
      teamFind.addEventListener("search", apply);
    }
    // Re-check the clock when the phone comes back to the page, and once a minute while it is
    // open, so a page left open at 7:29 turns gold at 7:30.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) apply();
    });
    setInterval(apply, 60 * 1000);

    apply();
    remember();
  }
})();
