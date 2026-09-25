(() => {
  const searchInput = document.getElementById("search");
  const categoriesEl = document.getElementById("categories");
  const sitesEl = document.getElementById("sites");
  const emptyEl = document.getElementById("empty");
  const resultCountEl = document.getElementById("result-count");

  let sites = [];
  let activeCategory = "All";

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
