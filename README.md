# TRMNL Cinema Plugin

## Overview

A plugin for [TRMNL displays](https://trmnl.com/) that shows the highest-rated movies currently screening in your city's cinemas. It reads the programme of any German city from [cinema.de](https://www.cinema.de/), ranks the films by their [Letterboxd](https://letterboxd.com/) rating and shows the top 3 with the showtimes that are still to come.

> **Note**: This is a personal learning project by a C++ developer exploring TRMNL plugin development. While functional, the code may not follow all best practices. Feedback, contributions, and suggestions are welcome!

![TRMNL Cinema Plugin Display](TRMNL_Cinema_Plugin_Screenshot.png)

## How It Works

The whole plugin runs on TRMNL's servers. There is no backend or scheduled job to host.

- **Data**: On every refresh (hourly), TRMNL runs [src/transform.py](src/transform.py) as a [serverless transform](https://help.trmnl.com/en/articles/14130649-serverless). It scrapes today's programme for the configured city from cinema.de.
- **Ranking**: Each film is looked up on Letterboxd. Ratings are cached in TRMNL's [Saved State](https://help.trmnl.com/en/articles/16777795-saved-state), so only new films are looked up.
- **Filtering**: Showtimes that already started are hidden; after the last screening of the day the plugin shows tomorrow's programme. With a Letterboxd username, films you logged recently are hidden.
- **Display**: Liquid templates for the full, half and quadrant layouts, in landscape and portrait, on TRMNL OG and TRMNL X.
- **Deployment**: Every push to `main` that touches the plugin is linted, tested and pushed to TRMNL by [GitHub Actions](.github/workflows/trmnl.yml) with [trmnlp](https://github.com/usetrmnl/trmnlp).

## Settings

| Field | Description |
|---|---|
| City | The city as cinema.de names it, e.g. `Leipzig`, `München` or `Frankfurt am Main`. A cinema.de programme URL works too, e.g. for `halle-saale`. |
| Letterboxd Username | Optional. Films you logged on Letterboxd recently are hidden. |
| Hide Films Watched Within (Days) | How far back your Letterboxd diary counts as recently watched. Default 180. |
| Preferred Cinemas | Optional. Listed first under each film, in this order. Part of the name is enough, e.g. `Schauburg`. |
| Excluded Cinemas | Optional. Screenings at these cinemas are hidden; a film shown only there drops out. Part of the name is enough. |

## Project Structure

```
cinema/
├── .github/workflows/
│   └── trmnl.yml                # Lint, test and push the plugin to TRMNL
├── bin/
│   └── trmnlp                   # Runs the trmnlp CLI in Docker
├── src/                         # The plugin as TRMNL stores it
│   ├── settings.yml             # Plugin settings and custom fields (pushed to TRMNL)
│   ├── transform.py             # Serverless transform: scraping, ranking, caching
│   ├── shared.liquid            # Styles and templates shared by all views
│   ├── full.liquid              # Full screen view
│   ├── half_horizontal.liquid   # Half views for mashups
│   ├── half_vertical.liquid
│   └── quadrant.liquid          # Quadrant view for mashups
├── tests/
│   ├── test_transform.py        # Unit tests for the transform (offline)
│   ├── plugin_spec.rb           # Rendering tests on all TRMNL devices (trmnlp test)
│   └── fixtures/                # Saved cinema.de page
├── .trmnlp.yml                  # Local preview settings (not pushed)
└── README.md
```

## Development

### Requirements

- [Docker](https://docs.docker.com/get-docker/) for `bin/trmnlp`
- Python 3.12 with `requests` for the unit tests (TRMNL's serverless runtime uses Python 3.12)

### Preview

```bash
bin/trmnlp serve        # live preview at http://localhost:4567, runs the real transform
bin/trmnlp build --png  # renders every view to _build/
```

The preview uses the custom field values from [.trmnlp.yml](.trmnlp.yml). Set `LETTERBOXD_USERNAME` in your environment to try the watched-films filter. On Windows, run `bin/trmnlp` from Git Bash.

### Tests

```bash
python -m unittest discover -s tests   # transform unit tests, no network needed
bin/trmnlp lint                        # TRMNL best practices
bin/trmnlp test --report report        # renders all views on all devices; open report/index.html
```

### Constraints of TRMNL's serverless runtime

- 5 seconds and 128 MB per run. The transform stops looking up films after 2.5 seconds and continues on the next refresh.
- Only `requests` and the Python standard library are available: HTML is parsed with `html.parser`, RSS with `xml.etree`.
- There is no time zone database, so German time is computed in `german_now()`.
- Saved State holds at most 8 KB. `build_state()` trims the rating cache to fit.

### Deployment

Pushes to `main` deploy automatically. The workflow needs the repository secret `TRMNL_API_KEY`: a TRMNL account API key with the `read` and `content` capabilities, created at [trmnl.com/account](https://trmnl.com/account). The plugin it updates is set by `id` in [src/settings.yml](src/settings.yml).

## Third-Party Assets

This project uses the **"theaters" icon from Material Symbols**: in TRMNL's orange as the plugin icon ([assets/theaters.svg](assets/theaters.svg), [assets/theaters.png](assets/theaters.png)) and inlined in the title bar  
© Google  
Licensed under the Apache License 2.0  
https://fonts.google.com/icons

Programme data comes from [cinema.de](https://www.cinema.de/), ratings and posters from [Letterboxd](https://letterboxd.com/).

## License

PolyForm Noncommercial 1.0.0 (no commercial use; attribution required)

See [LICENSE](LICENSE) (official text link) and [NOTICE](NOTICE) for attribution requirements.
