# TRMNL Cinema Plugin

## Overview

A plugin for [TRMNL displays](https://usetrmnl.com/) that shows the highest-rated movies currently screening in local German cinemas. The plugin automatically scrapes cinema screenings from [cinema.de](https://www.cinema.de/), filters them, and ranks them by their [Letterboxd](https://letterboxd.com/) ratings. It displays the top 3 movies along with their screening times and cinemas.

> **Note**: This is a personal learning project by a C++ developer exploring TRMNL plugin development. While functional, the code may not follow all best practices. Feedback, contributions, and suggestions are welcome!

## How It Works

- **Data Source**: Cinema screenings are scraped from cinema.de
- **Ranking**: Movies are ranked by Letterboxd user ratings
- **Display**: Shows the 3 highest-rated movies with showtimes for each cinema
- **Deployment**: Frontend is deployed via TRMNL, backend runs on a GitHub Actions schedule

## Project Architecture

- **Frontend**: Liquid template deployed directly through TRMNL's plugin system
- **Backend**: Python scripts run on a scheduled GitHub Actions cronjob to fetch and post data

## Project Structure

```
cinema/
├── .github/workflows/            # GitHub Actions workflows
│   └── nightly-run.yml          # Scheduled workflow to run scraper nightly
├── .vscode/                      # VS Code configuration
│   └── launch.json              # Debug and launch configurations
├── backend/                      # Python backend for data processing
│   ├── main.py                  # Manages data scraping, cleaning, and webhook posting
│   ├── config.json              # Configure the project
│   ├── ScreeningScraper.py      # Scrapes cinema screening data
│   ├── ScreeningDataCleanup.py  # Cleans and formats screening data
│   ├── LetterboxdAPIClient.py   # Letterboxd API integration for additional movie information
│   ├── PostToWebhook.py         # Sends data to TRMNL webhook
│   ├── requirements.txt         # Python dependencies
├── frontend/                     # Liquid template and development environment
│   ├── index.js                 # Renders Liquid template to HTML for development
│   ├── package.json             # Node.js dependencies
│   ├── src/
│   │   └── main.liquid          # Liquid template for rendering
│   ├── samples/
│   │   └── sample-data.json     # Sample cinema screening data for debugging purpose
└── README.md                     # This file
```

## Setup

### Backend Requirements

- Python 3.x
- Dependencies listed in `backend/requirements.txt`

### Frontend Requirements

- Node.js and npm

### Installation

#### Backend Setup

```bash
cd backend
pip install -r requirements.txt
```

#### Frontend Setup

```bash
cd frontend
npm install
```

### Configuration

#### Environment Variables

Set the TRMNL webhook URL as an environment variable:

```bash
set TRMNL_WEBHOOK_URL=your_webhook_url_here
```

#### Project Settings

Configure the backend behavior in `backend/config.json`:

```json
{
  "city": {
    "name": "NAME_OF_YOUR_CITY_USED_FOR_CINEMA_DE",
    "displayName": "NAME_OF_YOUR_CITY_AS_DISPLAYED_ON_THE_TRMNL_DEVICE"
  },
  "recentlyWatchedMovies": {
    "excludeWatchedMovies": true,
    "letterboxdUsername": "LETTERBOXD_USERNAME",
    "numberOfDaysForRecentWatches": 90
  }
}
```

## Usage

### Production Deployment

#### Backend
The backend runs automatically via a **GitHub Actions cronjob** that executes daily at 2:16 AM UTC (configured in [.github/workflows/nightly-run.yml](.github/workflows/nightly-run.yml)). It scrapes cinema screening data for the city defined in the config file, cleans it, and posts it to your TRMNL webhook URL.

**Note:** In production, both `config.json` and the TRMNL webhook URL are stored as GitHub repository secrets (`CONFIG_JSON` and `TRMNL_WEBHOOK_URL`).

#### Frontend
The frontend is deployed directly through the **TRMNL web interface**:
1. Create a new plugin in your TRMNL dashboard
2. Copy the Liquid code between the `<!-- Start TRMNL Code -->` and `<!-- End TRMNL Code -->` comments in [src/main.liquid](frontend/src/main.liquid)
3. Paste it into the TRMNL plugin editor

### Development & Debugging

#### VS Code Launch Configurations

This project includes pre-configured launch configurations for easy debugging and development. Access them via the **Run and Debug** view (Ctrl+Shift+D):

- **Backend** — Launches the backend Python script (`backend/main.py`) in the debugger
- **Frontend** — Builds the frontend once by running `index.js`
- **Frontend (watch)** — Starts the development server with continuous hot-reloading via `npm run dev`

#### Running the Backend Manually

```bash
python backend/main.py
```

This will:
1. Scrape cinema screening data
2. Clean and process the data
3. Post the formatted data to your TRMNL webhook URL

**Use this only for debugging the scraper or data cleaning logic.**

#### Building the Frontend HTML

```bash
cd frontend
npm run dev
```

This starts a development server with hot-reloading that watches for changes to:
- `src/main.liquid` (Liquid template)
- `data/data.json` (Cinema data)

**Use this only for debugging template changes before deploying to TRMNL.**

## Dependencies

### Backend
- **requests**: HTTP library for web scraping
- **bs4**: Beautiful Soup for HTML parsing

### Frontend
- **liquidjs**: JavaScript implementation of Liquid templating (v10.21.0)
- **nodemon**: Development tool for auto-reloading (dev dependency)

## Third-Party Assets

This project uses **Bootstrap Icons**  
© The Bootstrap Authors  
Licensed under the MIT License  
https://icons.getbootstrap.com/

## License

PolyForm Noncommercial 1.0.0 (no commercial use; attribution required)

See [LICENSE](LICENSE) (official text link) and [NOTICE](NOTICE) for attribution requirements.
