/* ============================================================================
   about-section-nav.js — progressive enhancement for the About section nav
   campaigns.healthsites.io

   Two behaviours, both optional (the nav is a working jump-menu without JS):
   1. Scrollspy — highlights the chip for the section currently in view.
   2. Open-on-jump — opens a collapsed <details> when you jump to its section,
      so the reader lands on content, not a closed accordion.

   Deliberately NO scrollIntoView and NO page scrolling from JS — the page
   scroll is handled natively by the anchor links + CSS scroll-margin-top.
   The only programmatic scroll here is horizontal, INSIDE the chip strip.

   Load once, deferred, after the markup:
     <script src="{{ SITEURL }}/theme/js/about-section-nav.js" defer></script>
   ============================================================================ */
(function () {
  "use strict";
  var nav = document.querySelector(".section-nav");
  if (!nav) return;

  var track = nav.querySelector(".section-nav__track");
  var links = Array.prototype.slice.call(nav.querySelectorAll(".section-nav__link"));
  if (!links.length) return;

  var byId = {};
  var targets = [];
  links.forEach(function (link) {
    var id = (link.getAttribute("href") || "").replace(/^#/, "");
    if (!id) return;
    byId[id] = link;
    var section = document.getElementById(id);
    if (section) targets.push(section);
  });

  function setActive(id) {
    links.forEach(function (l) {
      var on = l === byId[id];
      l.classList.toggle("is-active", on);
      if (on) { l.setAttribute("aria-current", "true"); }
      else { l.removeAttribute("aria-current"); }
    });
    // keep the active chip visible within the horizontal strip (nav only)
    var a = byId[id];
    if (a && track && track.scrollWidth > track.clientWidth) {
      var left = a.offsetLeft - (track.clientWidth - a.offsetWidth) / 2;
      track.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
    }
  }

  /* ---- scrollspy --------------------------------------------------------- */
  if ("IntersectionObserver" in window && targets.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) setActive(e.target.id);
      });
    }, { rootMargin: "-40% 0px -55% 0px", threshold: 0 });
    targets.forEach(function (t) { io.observe(t); });
  }

  /* ---- open the target <details> on jump --------------------------------- */
  links.forEach(function (link) {
    link.addEventListener("click", function () {
      var id = (link.getAttribute("href") || "").replace(/^#/, "");
      var heading = document.getElementById(id);
      if (!heading) return;
      var el = heading.nextElementSibling;
      while (el && el.tagName === "HR") el = el.nextElementSibling;
      if (el && el.tagName === "DETAILS") el.open = true;
      setActive(id);
      // page scroll happens natively via the anchor + scroll-margin-top
    });
  });
})();
