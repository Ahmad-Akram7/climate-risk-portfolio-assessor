# Limitations

CRPA results are screening estimates. They can support triage and data collection, but they should not be presented as exact, insurance-grade, actuarial, or regulatory results.

The largest current limitations are incomplete building exposure attributes, coarse or modeled hazard layers, limited Pakistan-specific vulnerability observations, no shared-event portfolio simulation, no validated AAL/PML engine, and no full CMIP6 downscaling workflow. Synthetic inputs are explicitly labelled and should not be used for decisions.

Further limits of the current scoring:

- The drought rating measures how long dry spells last (ETCCDI consecutive dry days from ERA5). It is not a drought-anomaly index such as SPI or SPEI, so a naturally arid site can rate high.
- Landslide is only rated when a local susceptibility raster is installed. Without it the hazard is "not assessed", not low.
- Wildfire from NASA FIRMS reflects detections in the last 10 days, not long-term fire probability, and is given low source quality.
- ERA5 gusts and temperatures are about 10 to 25 km averages and understate local extremes.
- Hazard probabilities are combined as if independent. Correlated events and portfolio-level accumulation are not modelled.
- Sea-level rise uses a US-only coastline model; outside the US only explicit coastal flood zones get the uplift.
- The consequence factor by asset class is a business-interruption proxy, not a measured value.

## Added with the API and commercial upgrade

The river indicator is the ratio of a 20-year peak flow to the median flow from GloFAS (about 5 km). It shows how flashy a river is. It is not flood depth at the site and does not enter the score or loss.

The CMIP6 scenario uses one model and one high-emissions pathway. There is no scenario selector and no uncertainty range across models.

The Open-Meteo climate, flood and geocoding calls and the paid `customer-*` hosts were not exercised against the live services during development. The parsing is covered by tests on synthetic responses.

The Open-Meteo free tier is non-commercial. Selling results needs a paid plan.

## Fragility calibration and building attributes

The default curves are not calibrated to any loss record. Wind damage probability is the probability at the worst daily gust in the record, so it is not an annual figure. With the default curve it only passes 85% above about 65 m/s.

Construction type, year built, height and stories shift the wind curve midpoint by assumed screening amounts (see `WIND_CONSTRUCTION_SHIFT` in `src/fragility.py`). These values are judgement, not fitted to data. Assets without these fields use the generic curve, and the `vulnerability_basis` column says which was used.

To calibrate with your own loss or claims data, create `data/calibration/fragility.json`, for example `{"wind": {"k": 0.2, "x0": 60, "max_loss": 0.35}}`. An invalid file is ignored with a warning. Public disaster totals such as EM-DAT are country-level and cannot calibrate asset-level curves on their own.

## Flood annual loss

`flood_aal_usd` is reported only when an asset has at least three flood return periods. With one raster (for example RP20) the engine reports `flood_event_loss_usd` and `flood_event_return_period` instead, and the portfolio AAL is left empty. Wind, heat and fire use the worst value in the climate record, so the combined score does not describe one common return period (see `loss_basis` in the summary).
