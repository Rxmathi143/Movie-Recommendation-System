# Movie Recommendation Frontend + Backend

This project wraps your TMDB recommendation code in a Flask backend and connects it to a full frontend page.

## Files

- `app.py` - Flask backend, recommendation models, and API routes.
- `templates/index.html` - Main frontend page.
- `static/styles.css` - Page styling.
- `static/app.js` - Frontend API calls and rendering.
- `requirements.txt` - Python packages.

## Add your dataset

Place these two files in this same folder:

- `tmdb_5000_credits.csv`
- `tmdb_5000_movies.csv`

If the files are missing, the app still runs with sample movies so you can test the page.

## Run

```powershell
pip install -r requirements.txt
python app.py
```

On Windows, if `python` is not recognized, try:

```powershell
py app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## API

- `GET /api/movies?q=dark`
- `GET /api/recommend?title=The Dark Knight Rises&mode=features`
- `GET /api/recommend?title=The Dark Knight Rises&mode=overview`
- `GET /api/popular`
- `GET /api/top-rated`

## Posters

The interface uses local poster files from `static/posters` whenever they exist. Movies without a downloaded poster automatically get a generated SVG poster in `static/posters/generated`, so the layout still looks complete and fast.

To download poster files for every movie in `tmdb_5000_movies.csv`, run:

```powershell
python download_posters.py --source tmdb --delay 1.2
```

The downloader saves files in `static/posters/downloaded` and writes progress to `static/posters/downloaded/manifest.csv`. It is resumable, so running it again skips posters that already exist.

To allow live online poster lookup for more titles, run:

```powershell
$env:ONLINE_POSTER_LOOKUP="1"
python app.py
```
