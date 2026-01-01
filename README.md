# EventMax — Local Events (ZIP-based)

A Streamlit application to browse local events by ZIP code and radius, powered by the Ticketmaster Discovery API.

## Features

- **Ticketmaster Source**: Discovery API for events by ZIP + radius
- **Month-Only Fetch**: Loads the current view month for speed
- **Instagram-like Feed**: Image-first cards with date/location
- **Map + Table**: Interactive markers and sortable table
- **Cheapest-First**: Sorts by price when available

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Recommended: do NOT hardcode keys in public repos. Use one of:

- Local: create a `.env` file with `TICKETMASTER_API_KEY=...`
- Streamlit Cloud: set `TICKETMASTER_API_KEY` under App → Settings → Secrets

### 3. Run Locally

```bash
streamlit run streamlit_app.py
```

On Windows you can also use:

```bat
run_dashboard.bat
```

## Deploy to Streamlit Cloud

1. Create a new GitHub repo (private recommended if committing secrets).
2. Push this folder to GitHub.
3. In Streamlit Cloud:
	- New app → Connect your repo
	- Main file: `streamlit_app.py`
	- Python version: 3.11+
	- Add secrets: set `TICKETMASTER_API_KEY`
4. Deploy.

Tip: keep `.env` and other secrets out of git (see `.gitignore`).

## Troubleshooting

**No events found:**
- Confirm your ZIP, radius, and date range
- Verify your Ticketmaster API key is set (in `.env` or the input)
- Check internet connectivity

**API errors or rate limits:**
- Recheck the key validity in your Ticketmaster developer portal
- Reduce the date range or radius

## Future Enhancements

- Category filters (music, sports, etc.)
- Export to CSV/JSON
- Calendar sync
