# Test data

`crpa_golden_test_portfolio.csv` is the five-asset fixture used for API integration checks. Its expected bands are qualitative because upstream services and datasets change.

Useful checks include:

- all five assets validate and keep unique IDs
- Florida and Texas wind scores exceed Denver
- Houston has meaningful flood exposure
- Los Angeles wildfire exposure exceeds Miami
- Florida and Texas heat scores exceed Denver
- replacement values survive ingestion
- every hazard result records a source, retrieval time, dataset or version, and confidence
- a successful API response never silently becomes synthetic data

The `sample_pakistan_*.csv` files are small offline fixtures for the Pakistan workflow. Templates show the accepted upload columns. Large rasters belong in local storage or a separately documented release, not in ordinary Git history.
