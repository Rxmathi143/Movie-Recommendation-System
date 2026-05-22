const movieInput = document.querySelector("#movieInput");
const movieOptions = document.querySelector("#movieOptions");
const recommendButton = document.querySelector("#recommendButton");
const recommendations = document.querySelector("#recommendations");
const resultsTitle = document.querySelector("#resultsTitle");
const statusText = document.querySelector("#statusText");
const popularChart = document.querySelector("#popularChart");
const topRated = document.querySelector("#topRated");
const modeButtons = document.querySelectorAll(".mode");

let activeMode = "features";

function setStatus(message, isError = false) {
  statusText.textContent = message;
  statusText.classList.toggle("error", isError);
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fallbackPoster(title) {
  return `/api/poster-fallback?title=${encodeURIComponent(title || "Movie")}`;
}

function posterImage(movie, className = "") {
  const title = movie.title || "Movie";
  const poster = movie.poster || fallbackPoster(title);
  const classAttr = className ? ` class="${escapeHtml(className)}"` : "";
  return `<img${classAttr} src="${escapeHtml(poster)}" alt="${escapeHtml(title)} poster" loading="lazy" onerror="this.onerror=null;this.src='${escapeHtml(fallbackPoster(title))}';" />`;
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function renderMovieCards(items) {
  recommendations.innerHTML = items
    .map((movie) => {
      const genres = movie.genres?.slice(0, 2).join(" / ") || "Movie";
      const cast = movie.cast?.slice(0, 2).join(", ") || "Cast unavailable";
      return `
        <article class="movie-card">
          <div class="poster-wrap">
            ${posterImage(movie)}
            <span class="rating-badge">${escapeHtml(String(movie.rating))}</span>
          </div>
          <div class="movie-info">
            <h3>${escapeHtml(movie.title)}</h3>
            <div class="meta">
              <span class="pill">${escapeHtml(genres)}</span>
              <span class="pill">${escapeHtml(String(movie.votes))} votes</span>
            </div>
            <p>${escapeHtml(movie.overview || "No overview available.")}</p>
            <p><strong>Director:</strong> ${escapeHtml(movie.director || "Unknown")}</p>
            <div class="footer">${escapeHtml(cast)}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderPopular(items) {
  const maxPopularity = Math.max(...items.map((movie) => movie.popularity), 1);
  popularChart.innerHTML = items
    .map((movie) => {
      const width = Math.max((movie.popularity / maxPopularity) * 100, 4);
      return `
        <div class="bar-row">
          ${posterImage(movie)}
          <span>${escapeHtml(movie.title)}</span>
          <div class="bar-track">
            <div class="bar-fill" style="width: ${width}%"></div>
          </div>
          <strong>${escapeHtml(String(movie.popularity))}</strong>
        </div>
      `;
    })
    .join("");
}

function renderTopRated(items) {
  topRated.innerHTML = items
    .map(
      (movie, index) => `
        <article class="rank-item">
          <span class="rank-number">${index + 1}</span>
          ${posterImage(movie)}
          <div>
            <p class="rank-title">${escapeHtml(movie.title)}</p>
            <p class="rank-subtitle">${escapeHtml(String(movie.votes))} votes</p>
          </div>
          <span class="score">${escapeHtml(String(movie.score))}</span>
        </article>
      `,
    )
    .join("");
}

async function loadMovieOptions(query = "") {
  const titles = await fetchJson(`/api/movies?q=${encodeURIComponent(query)}`);
  movieOptions.innerHTML = titles
    .map((title) => `<option value="${escapeHtml(title)}"></option>`)
    .join("");
  if (!movieInput.value && titles.length) {
    movieInput.placeholder = `Try ${titles[0]}`;
  }
}

async function loadDashboard() {
  const [popular, rated, status] = await Promise.all([
    fetchJson("/api/popular"),
    fetchJson("/api/top-rated"),
    fetchJson("/api/status"),
  ]);
  renderPopular(popular);
  renderTopRated(rated);
  setStatus(
    status.using_sample
      ? `Running with ${status.movie_count} sample movies. Add the two TMDB CSV files for the full dataset.`
      : `Loaded ${status.movie_count} movies from your TMDB CSV files.`,
  );
}

async function recommend() {
  const title = movieInput.value.trim();
  if (!title) {
    setStatus("Type a movie title first.", true);
    movieInput.focus();
    return;
  }

  recommendButton.disabled = true;
  recommendButton.textContent = "Finding...";
  try {
    const data = await fetchJson(
      `/api/recommend?title=${encodeURIComponent(title)}&mode=${activeMode}`,
    );
    resultsTitle.textContent = `Because you chose ${data.title}`;
    renderMovieCards(data.results);
    setStatus(`Showing ${data.results.length} recommendations using ${activeMode}.`);
  } catch (error) {
    recommendations.innerHTML = "";
    resultsTitle.textContent = "No recommendations found";
    setStatus(error.message, true);
  } finally {
    recommendButton.disabled = false;
    recommendButton.textContent = "Recommend";
  }
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    modeButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeMode = button.dataset.mode;
  });
});

movieInput.addEventListener("input", () => {
  loadMovieOptions(movieInput.value).catch(() => {});
});

movieInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    recommend();
  }
});

recommendButton.addEventListener("click", recommend);

loadMovieOptions().catch(() => setStatus("Could not load movie titles.", true));
loadDashboard().catch((error) => setStatus(error.message, true));
