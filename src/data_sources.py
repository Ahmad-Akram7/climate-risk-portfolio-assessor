"""Public data services CRPA can use, with where to get access. Used by the dashboard and the docs."""
from __future__ import annotations

SERVICES = [
    {"id": "open-meteo", "name": "Open-Meteo", "env": "OPEN_METEO_API_KEY", "needs_key": False,
     "gives": "Wind and heat extremes (ERA5), dry spells, river discharge (GloFAS), CMIP6 climate change signal, elevation, place lookup",
     "terms": "Free without a key for non-commercial use. Selling results needs a paid plan and a key.",
     "link": "https://open-meteo.com/en/pricing", "link_label": "Commercial plan"},
    {"id": "noaa", "name": "NOAA Climate Data Online", "env": "NOAA_CDO_TOKEN", "needs_key": True,
     "gives": "Station temperature records (United States)", "terms": "Free token by email.",
     "link": "https://www.ncdc.noaa.gov/cdo-web/token", "link_label": "Get a free token"},
    {"id": "firms", "name": "NASA FIRMS", "env": "NASA_FIRMS_KEY", "needs_key": True,
     "gives": "Active fire detections from the last 10 days", "terms": "Free map key.",
     "link": "https://firms.modaps.eosdis.nasa.gov/api/map_key/", "link_label": "Get a free key"},
    {"id": "opentopo", "name": "OpenTopography", "env": "OPENTOPOGRAPHY_API_KEY", "needs_key": True,
     "gives": "30 m Copernicus elevation", "terms": "Free account and key.",
     "link": "https://portal.opentopography.org/requestService?service=api", "link_label": "Get a free key"},
    {"id": "nvidia", "name": "NVIDIA API catalog", "env": "NVIDIA_API_KEY", "needs_key": True,
     "gives": "AI-written analyst narrative in the report (optional)", "terms": "Free tier with an account. A portfolio summary is sent to the provider.",
     "link": "https://build.nvidia.com", "link_label": "Get a key"},
]
