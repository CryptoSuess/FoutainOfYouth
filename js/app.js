(() => {
  const searchInput = document.getElementById("search");
  const categoriesEl = document.getElementById("categories");
  const sitesEl = document.getElementById("sites");
  const emptyEl = document.getElementById("empty");
  const resultCountEl = document.getElementById("result-count");
  const previewEl = document.getElementById("site-preview");
  const previewLabelEl = document.getElementById("site-preview-label");
  const previewImageEl = document.getElementById("site-preview-image");
  const previewLoadingEl = document.getElementById("site-preview-loading");
  const previewFallbackEl = document.getElementById("site-preview-fallback");

  let sites = [];
  let activeCategory = "All";
  let previewShowTimer = null;
  let previewHideTimer = null;
  let activePreviewCard = null;

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function uniqueCategories(list) {
    return ["All", ...new Set(list.map((site) => site.category).filter(Boolean))].sort(
      (a, b) => {
        if (a === "All") return -1;
        if (b === "All") return 1;
        return a.localeCompare(b);
      }
    );
  }

  function matchesQuery(site, query) {
    if (!query) return true;
    const haystack = [
      site.name,
      site.description,
      site.category,
      ...(site.tags || []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  }

  function filteredSites() {
    const query = searchInput.value.trim().toLowerCase();
    return sites.filter((site) => {
      const categoryOk =
        activeCategory === "All" || site.category === activeCategory;
      return categoryOk && matchesQuery(site, query);
    });
  }

  function previewImageUrl(siteUrl) {
    // Free screenshot thumbnail service; loads only on hover.
    return `https://image.thum.io/get/width/720/crop/450/noanimate/${siteUrl}`;
  }

  function clearPreviewTimers() {
    window.clearTimeout(previewShowTimer);
    window.clearTimeout(previewHideTimer);
    previewShowTimer = null;
    previewHideTimer = null;
  }

  function setPreviewState(state) {
    previewLoadingEl.hidden = state !== "loading";
    previewImageEl.hidden = state !== "ready";
    previewFallbackEl.hidden = state !== "fallback";
  }

  function hidePreview() {
    clearPreviewTimers();
    activePreviewCard = null;
    previewEl.hidden = true;
    previewEl.setAttribute("aria-hidden", "true");
    previewImageEl.removeAttribute("src");
    previewImageEl.onload = null;
    previewImageEl.onerror = null;
    setPreviewState("loading");
  }

  function positionPreview(card) {
    const gap = 12;
    const rect = card.getBoundingClientRect();
    const previewWidth = Math.min(360, window.innerWidth - 24);
    const previewHeight = previewEl.offsetHeight || 260;

    let left = rect.left + rect.width / 2 - previewWidth / 2;
    left = Math.max(12, Math.min(left, window.innerWidth - previewWidth - 12));

    let top = rect.top - previewHeight - gap;
    if (top < 12) {
      top = rect.bottom + gap;
    }

    previewEl.style.width = `${previewWidth}px`;
    previewEl.style.left = `${left}px`;
    previewEl.style.top = `${top}px`;
  }

  function showPreview(card) {
    const url = card.href;
    const name = card.dataset.name || "Site preview";

    activePreviewCard = card;
    previewLabelEl.textContent = name;
    previewImageEl.alt = `Preview of ${name}`;
    setPreviewState("loading");

    const imageUrl = previewImageUrl(url);
    previewImageEl.onload = () => {
      if (activePreviewCard !== card) return;
      if (!previewImageEl.naturalWidth) {
        setPreviewState("fallback");
      } else {
        setPreviewState("ready");
      }
      positionPreview(card);
    };
    previewImageEl.onerror = () => {
      if (activePreviewCard !== card) return;
      setPreviewState("fallback");
      positionPreview(card);
    };

    // Force reload if hovering the same card again.
    previewImageEl.src = "";
    previewImageEl.src = imageUrl;
    previewEl.hidden = false;
    previewEl.setAttribute("aria-hidden", "false");
    positionPreview(card);
  }

  function scheduleShowPreview(card) {
    clearPreviewTimers();
    previewShowTimer = window.setTimeout(() => {
      showPreview(card);
    }, 220);
  }

  function scheduleHidePreview() {
    clearPreviewTimers();
    previewHideTimer = window.setTimeout(() => {
      hidePreview();
    }, 120);
  }

  function renderCategories() {
    const categories = uniqueCategories(sites);
    categoriesEl.innerHTML = categories
      .map(
        (category) => `
        <button
          type="button"
          class="category-btn"
          data-category="${escapeHtml(category)}"
          aria-pressed="${category === activeCategory}"
        >
          ${escapeHtml(category)}
        </button>`
      )
      .join("");
  }

  function renderSites() {
    hidePreview();
    const results = filteredSites();
    resultCountEl.textContent =
      results.length === 1
        ? "1 site"
        : `${results.length} sites`;

    if (results.length === 0) {
      sitesEl.innerHTML = "";
      emptyEl.hidden = false;
      return;
    }

    emptyEl.hidden = true;
    sitesEl.innerHTML = results
      .map((site, index) => {
        const tags = (site.tags || [])
          .slice(0, 4)
          .map((tag) => `<li>${escapeHtml(tag)}</li>`)
          .join("");

        return `
          <a
            class="site-card"
            href="${escapeHtml(site.url)}"
            target="_blank"
            rel="noopener noreferrer"
            data-name="${escapeHtml(site.name)}"
            style="animation-delay: ${Math.min(index, 12) * 35}ms"
          >
            <div class="site-meta">
              <span class="site-category">${escapeHtml(site.category)}</span>
              <span class="site-arrow" aria-hidden="true">→</span>
            </div>
            <h2 class="site-name">${escapeHtml(site.name)}</h2>
            <p class="site-description">${escapeHtml(site.description)}</p>
            ${tags ? `<ul class="site-tags">${tags}</ul>` : ""}
          </a>`;
      })
      .join("");

    bindCardPreviewHandlers();
  }

  function bindCardPreviewHandlers() {
    sitesEl.querySelectorAll(".site-card").forEach((card) => {
      card.addEventListener("mouseenter", () => {
        scheduleShowPreview(card);
      });
      card.addEventListener("mouseleave", () => {
        scheduleHidePreview();
      });
      card.addEventListener("focus", () => {
        scheduleShowPreview(card);
      });
      card.addEventListener("blur", () => {
        scheduleHidePreview();
      });
    });
  }

  function render() {
    renderCategories();
    renderSites();
  }

  categoriesEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-category]");
    if (!button) return;
    activeCategory = button.dataset.category;
    render();
  });

  searchInput.addEventListener("input", () => {
    renderSites();
  });

  window.addEventListener("scroll", () => {
    if (!previewEl.hidden && activePreviewCard) {
      positionPreview(activePreviewCard);
    }
  }, { passive: true });

  window.addEventListener("resize", hidePreview);

  async function init() {
    try {
      const response = await fetch("data/sites.json");
      if (!response.ok) {
        throw new Error(`Failed to load sites (${response.status})`);
      }
      const payload = await response.json();
      sites = Array.isArray(payload)
        ? payload
        : Array.isArray(payload.sites)
          ? payload.sites
          : [];
      sites.sort((a, b) => a.name.localeCompare(b.name));
      render();
    } catch (error) {
      console.error(error);
      resultCountEl.textContent = "Could not load the library.";
      emptyEl.hidden = false;
      emptyEl.textContent =
        "The site list could not be loaded. Check data/sites.json and try again.";
    }
  }

  init();
})();
