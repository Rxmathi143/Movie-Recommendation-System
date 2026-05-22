from ast import literal_eval
import os
from pathlib import Path
import json
import re
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
from flask import Flask, Response, jsonify, render_template, request
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity, linear_kernel


BASE_DIR = Path(__file__).resolve().parent
CREDITS_CSV = BASE_DIR / "tmdb_5000_credits.csv"
MOVIES_CSV = BASE_DIR / "tmdb_5000_movies.csv"
POSTER_DIR = BASE_DIR / "static" / "posters"
DOWNLOADED_POSTER_DIR = POSTER_DIR / "downloaded"
GENERATED_POSTER_DIR = POSTER_DIR / "generated"

app = Flask(__name__)
poster_cache = {}
ONLINE_POSTER_LOOKUP = os.environ.get("ONLINE_POSTER_LOOKUP") == "1"
KNOWN_POSTERS = {
    "Avatar": "https://upload.wikimedia.org/wikipedia/en/b/b0/Avatar-Teaser-Poster.jpg",
    "Batman Begins": "https://upload.wikimedia.org/wikipedia/en/a/af/Batman_Begins_Poster.jpg",
    "Batman v Superman: Dawn of Justice": "https://upload.wikimedia.org/wikipedia/en/2/20/Batman_v_Superman_poster.jpg",
    "Big Hero 6": "https://upload.wikimedia.org/wikipedia/en/4/4b/Big_Hero_6_%28film%29_poster.jpg",
    "Captain America: Civil War": "https://upload.wikimedia.org/wikipedia/en/5/53/Captain_America_Civil_War_poster.jpg",
    "Deadpool": "https://upload.wikimedia.org/wikipedia/en/thumb/2/23/Deadpool_%282016_poster%29.png/500px-Deadpool_%282016_poster%29.png",
    "Dawn of the Planet of the Apes": "https://upload.wikimedia.org/wikipedia/en/7/77/Dawn_of_the_Planet_of_the_Apes.jpg",
    "Fight Club": "https://upload.wikimedia.org/wikipedia/en/f/fc/Fight_Club_poster.jpg",
    "Forrest Gump": "https://upload.wikimedia.org/wikipedia/en/6/67/Forrest_Gump_poster.jpg",
    "Frozen": "https://upload.wikimedia.org/wikipedia/en/0/05/Frozen_%282013_film%29_poster.jpg",
    "Guardians of the Galaxy": "https://upload.wikimedia.org/wikipedia/en/thumb/3/33/Guardians_of_the_Galaxy_%28film%29_poster.jpg/500px-Guardians_of_the_Galaxy_%28film%29_poster.jpg",
    "Inception": "https://upload.wikimedia.org/wikipedia/en/7/7f/Inception_ver3.jpg",
    "Interstellar": "https://upload.wikimedia.org/wikipedia/en/b/bc/Interstellar_film_poster.jpg",
    "Jurassic World": "https://upload.wikimedia.org/wikipedia/en/6/6e/Jurassic_World_poster.jpg",
    "Mad Max: Fury Road": "https://upload.wikimedia.org/wikipedia/en/6/6e/Mad_Max_Fury_Road.jpg",
    "Minions": "https://upload.wikimedia.org/wikipedia/en/1/19/Minions_%282015_film%29.jpg",
    "Pirates of the Caribbean: The Curse of the Black Pearl": "https://upload.wikimedia.org/wikipedia/en/8/89/Pirates_of_the_Caribbean_-_The_Curse_of_the_Black_Pearl.png",
    "Pulp Fiction": "https://upload.wikimedia.org/wikipedia/en/8/82/Pulp_Fiction_cover.jpg",
    "Schindler's List": "https://upload.wikimedia.org/wikipedia/en/3/38/Schindler%27s_List_movie.jpg",
    "Spirited Away": "https://upload.wikimedia.org/wikipedia/en/3/30/Spirited_Away_poster.JPG",
    "The Shawshank Redemption": "https://upload.wikimedia.org/wikipedia/en/8/81/ShawshankRedemptionMoviePoster.jpg",
    "The Dark Knight": "https://upload.wikimedia.org/wikipedia/en/8/8a/Dark_Knight.jpg",
    "The Dark Knight Rises": "https://upload.wikimedia.org/wikipedia/en/8/83/Dark_knight_rises_poster.jpg",
    "The Godfather": "https://upload.wikimedia.org/wikipedia/en/1/1c/Godfather_ver1.jpg",
    "The Godfather: Part II": "https://upload.wikimedia.org/wikipedia/en/0/03/Godfather_part_ii.jpg",
    "The Martian": "https://upload.wikimedia.org/wikipedia/en/c/cd/The_Martian_film_poster.jpg",
    "Whiplash": "https://upload.wikimedia.org/wikipedia/en/0/01/Whiplash_poster.jpg",
}
LOCAL_POSTER_FILES = {
    "Avatar": "avatar.jpg",
    "Batman Begins": "batman-begins.jpg",
    "Batman v Superman: Dawn of Justice": "batman-v-superman.jpg",
    "Big Hero 6": "big-hero-6.jpg",
    "Captain America: Civil War": "captain-america-civil-war.jpg",
    "Dawn of the Planet of the Apes": "dawn-planet-apes.jpg",
    "Deadpool": "deadpool.png",
    "Fight Club": "fight-club.jpg",
    "Forrest Gump": "forrest-gump.jpg",
    "Frozen": "frozen.jpg",
    "Guardians of the Galaxy": "guardians-galaxy.jpg",
    "Inception": "inception.jpg",
    "Interstellar": "interstellar.jpg",
    "Jurassic World": "jurassic-world.jpg",
    "Mad Max: Fury Road": "mad-max-fury-road.jpg",
    "Minions": "minions.jpg",
    "Pirates of the Caribbean: The Curse of the Black Pearl": "pirates-black-pearl.png",
    "Pulp Fiction": "pulp-fiction.jpg",
    "Schindler's List": "schindlers-list.jpg",
    "Spirited Away": "spirited-away.jpg",
    "The Dark Knight": "the-dark-knight.jpg",
    "The Dark Knight Rises": "the-dark-knight-rises.jpg",
    "The Godfather": "the-godfather.jpg",
    "The Godfather: Part II": "the-godfather-part-ii.jpg",
    "The Martian": "the-martian.jpg",
    "The Shawshank Redemption": "shawshank.jpg",
    "Whiplash": "whiplash.jpg",
}


def fallback_poster(title):
    return local_generated_poster_url(title)


def svg_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def poster_lines(title, max_chars=18, max_lines=5):
    words = str(title).replace(":", " :").split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word[:max_chars]
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or ["Movie"]


def slugify_title(title):
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")
    return slug or "movie"


def poster_svg(title):
    lines = poster_lines(title)
    start_y = 330 - (len(lines) - 1) * 31
    text = "\n".join(
        f'<text x="250" y="{start_y + index * 62}" text-anchor="middle">{svg_escape(line)}</text>'
        for index, line in enumerate(lines)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="500" height="750" viewBox="0 0 500 750">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#121722"/>
      <stop offset="42%" stop-color="#1f2b38"/>
      <stop offset="100%" stop-color="#3b2432"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="18%" r="70%">
      <stop offset="0%" stop-color="#4fc3b7" stop-opacity=".55"/>
      <stop offset="70%" stop-color="#4fc3b7" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="500" height="750" fill="url(#bg)"/>
  <rect width="500" height="750" fill="url(#glow)"/>
  <circle cx="410" cy="88" r="92" fill="#ffbf5f" opacity=".28"/>
  <circle cx="84" cy="650" r="120" fill="#4fc3b7" opacity=".16"/>
  <rect x="42" y="52" width="416" height="646" rx="24" fill="none" stroke="#f7f4ee" stroke-opacity=".24" stroke-width="2"/>
  <g fill="#f7f4ee" font-family="Inter, Arial, sans-serif" font-size="46" font-weight="800">
    {text}
  </g>
  <text x="250" y="664" text-anchor="middle" fill="#ffbf5f" font-family="Inter, Arial, sans-serif" font-size="20" font-weight="800">MOVIE RECOMMENDER</text>
</svg>"""


def local_generated_poster_url(title):
    GENERATED_POSTER_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify_title(title)}.svg"
    path = GENERATED_POSTER_DIR / filename
    if not path.exists():
        path.write_text(poster_svg(title), encoding="utf-8")
    return f"/static/posters/generated/{filename}"


def downloaded_poster_path(movie_id, title):
    slug = slugify_title(title)
    prefix = f"{int(movie_id)}-{slug}" if pd.notna(movie_id) else slug
    for extension in ("jpg", "jpeg", "png", "webp"):
        path = DOWNLOADED_POSTER_DIR / f"{prefix}.{extension}"
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def local_downloaded_poster_url(movie_id, title):
    downloaded_path = downloaded_poster_path(movie_id, title)
    if downloaded_path:
        return f"/static/posters/downloaded/{downloaded_path.name}"

    filename = LOCAL_POSTER_FILES.get(title)
    if not filename:
        return ""
    path = POSTER_DIR / filename
    if path.exists() and path.stat().st_size > 0:
        return f"/static/posters/{filename}"
    return ""


def tmdb_poster_url(movie_id, title):
    if movie_id in poster_cache:
        return poster_cache[movie_id]

    poster_url = fallback_poster(title)
    page_url = f"https://www.themoviedb.org/movie/{int(movie_id)}"
    request = Request(
        page_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )

    try:
        with urlopen(request, timeout=4) as response:
            html = response.read(1_500_000).decode("utf-8", errors="ignore")
        match = re.search(
            r'<meta\s+property="og:image"\s+content="([^"]+)"',
            html,
            flags=re.IGNORECASE,
        )
        if match and "image.tmdb.org/t/p/" in match.group(1):
            poster_url = match.group(1).replace("/w600_and_h900_bestv2/", "/w500/")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        pass

    poster_cache[movie_id] = poster_url
    return poster_url


def wikipedia_poster_url(title):
    cache_key = f"wiki:{title}"
    if cache_key in poster_cache:
        return poster_cache[cache_key]

    candidates = [title, f"{title} (film)"]
    if ":" in title:
        candidates.append(f"{title.replace(':', '')} (film)")

    for candidate in candidates:
        api_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&titles={quote(candidate)}&prop=pageimages"
            "&format=json&pithumbsize=500&origin=*"
        )
        request = Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
            pages = payload.get("query", {}).get("pages", {})
            for page in pages.values():
                source = page.get("thumbnail", {}).get("source")
                if source:
                    poster_cache[cache_key] = source
                    return source
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError):
            continue

    poster_cache[cache_key] = ""
    return ""


def poster_url(movie_id, title):
    local_poster = local_downloaded_poster_url(movie_id, title)
    if local_poster:
        return local_poster
    if ONLINE_POSTER_LOOKUP:
        return (
            wikipedia_poster_url(title)
            or tmdb_poster_url(movie_id, title)
            or local_generated_poster_url(title)
        )
    return fallback_poster(title)


def sample_movies():
    """Small fallback dataset so the site runs before the TMDB CSVs are added."""
    rows = [
        {
            "id": 1,
            "title_x": "The Dark Knight Rises",
            "overview": "Batman returns to save Gotham from a masked revolutionary.",
            "vote_average": 7.6,
            "vote_count": 9106,
            "popularity": 112.3,
            "genres": [{"name": "Action"}, {"name": "Crime"}, {"name": "Drama"}],
            "keywords": [{"name": "superhero"}, {"name": "gotham"}, {"name": "vigilante"}],
            "cast": [{"name": "Christian Bale"}, {"name": "Tom Hardy"}, {"name": "Anne Hathaway"}],
            "crew": [{"job": "Director", "name": "Christopher Nolan"}],
        },
        {
            "id": 2,
            "title_x": "The Dark Knight",
            "overview": "Batman faces the Joker, a criminal who wants Gotham to burn.",
            "vote_average": 8.2,
            "vote_count": 12002,
            "popularity": 123.1,
            "genres": [{"name": "Action"}, {"name": "Crime"}, {"name": "Drama"}],
            "keywords": [{"name": "joker"}, {"name": "gotham"}, {"name": "chaos"}],
            "cast": [{"name": "Christian Bale"}, {"name": "Heath Ledger"}, {"name": "Aaron Eckhart"}],
            "crew": [{"job": "Director", "name": "Christopher Nolan"}],
        },
        {
            "id": 3,
            "title_x": "Batman Begins",
            "overview": "Bruce Wayne trains to become Batman and protect Gotham City.",
            "vote_average": 7.5,
            "vote_count": 7359,
            "popularity": 89.7,
            "genres": [{"name": "Action"}, {"name": "Crime"}],
            "keywords": [{"name": "origin"}, {"name": "superhero"}, {"name": "gotham"}],
            "cast": [{"name": "Christian Bale"}, {"name": "Michael Caine"}, {"name": "Liam Neeson"}],
            "crew": [{"job": "Director", "name": "Christopher Nolan"}],
        },
        {
            "id": 4,
            "title_x": "The Godfather",
            "overview": "The aging patriarch of a crime dynasty transfers control to his son.",
            "vote_average": 8.4,
            "vote_count": 5893,
            "popularity": 143.7,
            "genres": [{"name": "Drama"}, {"name": "Crime"}],
            "keywords": [{"name": "mafia"}, {"name": "family"}, {"name": "crime"}],
            "cast": [{"name": "Marlon Brando"}, {"name": "Al Pacino"}, {"name": "James Caan"}],
            "crew": [{"job": "Director", "name": "Francis Ford Coppola"}],
        },
        {
            "id": 5,
            "title_x": "The Godfather: Part II",
            "overview": "The Corleone story continues across two generations of power.",
            "vote_average": 8.3,
            "vote_count": 3338,
            "popularity": 105.8,
            "genres": [{"name": "Drama"}, {"name": "Crime"}],
            "keywords": [{"name": "mafia"}, {"name": "family"}, {"name": "revenge"}],
            "cast": [{"name": "Al Pacino"}, {"name": "Robert De Niro"}, {"name": "Diane Keaton"}],
            "crew": [{"job": "Director", "name": "Francis Ford Coppola"}],
        },
        {
            "id": 6,
            "title_x": "Inception",
            "overview": "A thief enters dreams to steal secrets and plant an idea.",
            "vote_average": 8.1,
            "vote_count": 13752,
            "popularity": 167.6,
            "genres": [{"name": "Action"}, {"name": "Science Fiction"}, {"name": "Adventure"}],
            "keywords": [{"name": "dream"}, {"name": "subconscious"}, {"name": "heist"}],
            "cast": [{"name": "Leonardo DiCaprio"}, {"name": "Joseph Gordon-Levitt"}, {"name": "Elliot Page"}],
            "crew": [{"job": "Director", "name": "Christopher Nolan"}],
        },
    ]
    return pd.DataFrame(rows)


def parse_feature(value):
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    try:
        parsed = literal_eval(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, SyntaxError):
        return []


def get_director(crew):
    for person in crew:
        if person.get("job") == "Director":
            return person.get("name", "")
    return ""


def get_top_names(items):
    return [item.get("name", "") for item in items[:3] if item.get("name")]


def clean_token(value):
    return str(value).lower().replace(" ", "")


def load_movies():
    using_sample = not (CREDITS_CSV.exists() and MOVIES_CSV.exists())

    if using_sample:
        movies = sample_movies()
    else:
        credits = pd.read_csv(CREDITS_CSV)
        movies = pd.read_csv(MOVIES_CSV)

        credits = credits.rename(columns={"movie_id": "id"})
        required_credit_columns = {"id", "title", "cast", "crew"}
        required_movie_columns = {
            "id",
            "title",
            "overview",
            "vote_average",
            "vote_count",
            "popularity",
            "keywords",
            "genres",
        }
        missing_credit_columns = required_credit_columns - set(credits.columns)
        missing_movie_columns = required_movie_columns - set(movies.columns)
        if missing_credit_columns or missing_movie_columns:
            raise ValueError(
                "CSV files do not match the TMDB 5000 format. "
                f"Missing credits columns: {sorted(missing_credit_columns)}. "
                f"Missing movies columns: {sorted(missing_movie_columns)}."
            )

        movies = movies.merge(credits, on="id")

    for column in ["cast", "crew", "keywords", "genres"]:
        movies[column] = movies[column].apply(parse_feature)

    movies["overview"] = movies["overview"].fillna("")
    movies["director"] = movies["crew"].apply(get_director)
    movies["cast_names"] = movies["cast"].apply(get_top_names)
    movies["keyword_names"] = movies["keywords"].apply(get_top_names)
    movies["genre_names"] = movies["genres"].apply(get_top_names)

    movies["soup"] = movies.apply(
        lambda row: " ".join(
            [clean_token(x) for x in row["keyword_names"]]
            + [clean_token(x) for x in row["cast_names"]]
            + [clean_token(row["director"])]
            + [clean_token(x) for x in row["genre_names"]]
        ),
        axis=1,
    )

    title_column = "title_x" if "title_x" in movies.columns else "title"
    movies["display_title"] = movies[title_column]
    movies = movies.reset_index(drop=True)

    vote_average = movies["vote_average"].fillna(0)
    vote_count = movies["vote_count"].fillna(0)
    c_value = vote_average.mean()
    m_value = vote_count.quantile(0.9) if len(movies) > 1 else 0
    denominator = vote_count + m_value
    movies["score"] = np.where(
        denominator > 0,
        (vote_count / denominator * vote_average) + (m_value / denominator * c_value),
        vote_average,
    )

    tfidf = TfidfVectorizer(stop_words="english")
    tfidf_matrix = tfidf.fit_transform(movies["overview"])
    overview_similarity = linear_kernel(tfidf_matrix, tfidf_matrix)

    count = CountVectorizer(stop_words="english")
    count_matrix = count.fit_transform(movies["soup"])
    feature_similarity = cosine_similarity(count_matrix, count_matrix)

    return {
        "movies": movies,
        "indices": pd.Series(movies.index, index=movies["display_title"]).drop_duplicates(),
        "overview_similarity": overview_similarity,
        "feature_similarity": feature_similarity,
        "using_sample": using_sample,
    }


movie_store = load_movies()


def movie_card(row, score=None):
    title = row["display_title"]
    return {
        "title": title,
        "overview": row.get("overview", ""),
        "rating": round(float(row.get("vote_average", 0)), 1),
        "votes": int(row.get("vote_count", 0)),
        "popularity": round(float(row.get("popularity", 0)), 1),
        "score": round(float(score if score is not None else row.get("score", 0)), 3),
        "director": row.get("director", ""),
        "cast": row.get("cast_names", []),
        "genres": row.get("genre_names", []),
        "poster": poster_url(row.get("id", 0), title),
    }


def recommendations_for(title, mode):
    store = movie_store
    indices = store["indices"]
    if title not in indices:
        matches = [
            movie
            for movie in store["movies"]["display_title"].tolist()
            if title.lower() in movie.lower()
        ]
        if matches:
            title = matches[0]
        else:
            return None

    similarity = (
        store["feature_similarity"] if mode == "features" else store["overview_similarity"]
    )
    idx = int(indices[title])
    scores = sorted(enumerate(similarity[idx]), key=lambda item: item[1], reverse=True)[1:11]
    return [movie_card(store["movies"].iloc[i], score) for i, score in scores]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def status():
    return jsonify(
        {
            "movie_count": int(len(movie_store["movies"])),
            "using_sample": movie_store["using_sample"],
        }
    )


@app.route("/api/poster-fallback")
def poster_fallback():
    title = request.args.get("title", "Movie").strip() or "Movie"
    return Response(poster_svg(title), mimetype="image/svg+xml")


@app.route("/api/movies")
def movies():
    query = request.args.get("q", "").strip().lower()
    titles = movie_store["movies"]["display_title"].tolist()
    if query:
        titles = [title for title in titles if query in title.lower()]
    return jsonify(titles[:40])


@app.route("/api/top-rated")
def top_rated():
    ranked = movie_store["movies"].sort_values("score", ascending=False).head(10)
    return jsonify([movie_card(row) for _, row in ranked.iterrows()])


@app.route("/api/popular")
def popular():
    ranked = movie_store["movies"].sort_values("popularity", ascending=False).head(8)
    return jsonify([movie_card(row) for _, row in ranked.iterrows()])


@app.route("/api/recommend")
def recommend():
    title = request.args.get("title", "").strip()
    mode = request.args.get("mode", "features")
    if not title:
        return jsonify({"error": "Please provide a movie title."}), 400

    results = recommendations_for(title, mode)
    if results is None:
        return jsonify({"error": f"No movie found for '{title}'."}), 404
    return jsonify({"title": title, "mode": mode, "results": results})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
