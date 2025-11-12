# emby_lists

Small utilities to provide Emby lists via email. The repository contains two scripts:

- `app/embylistsmoviesbymail.py` — send movie lists by mail when an authorized sender emails the configured keyword.
- `app/embylistsseriesbymail.py` — same as above, for series lists.

Requirements
-----------

Python 3.8+ and the packages listed in `requirements.txt` (install with pip).

Quick start
-----------

1. Copy `app/embylists.ini.example` to `/config/embylists.ini` or set `EMBYLISTS_CONFIG_DIR` to a different directory and place the file there.
2. Edit the INI with your mail and pushover settings.
3. Run the desired script: `python3 app/embylistsmoviesbymail.py` (or the series script).

Notes
-----

These scripts expect files such as `movieslist.txt`/`serieslist.txt` to live in the same config directory. Logs are written under `/var/log/` by default; override with the `EMBYLISTS_LOG_DIR` environment variable.
