# CRPA model card

## Current release

CRPA is a transparent screening model for portfolio climate risk. The current release labels its results `SCREENING` and records a quality gate in the output metadata.

## What it uses

The pipeline validates asset locations and values, records optional exposure attributes, attaches hazard observations from local layers or configured APIs, and calculates hazard probabilities, risk tiers, and scenario loss.

## What it does not claim

The current release is not a calibrated catastrophe model, actuarial annual-loss model, insurance quote, regulatory determination, or exact property-loss estimate. Missing exposure data is not silently treated as observed data.

## Model tiers

- `DEMO`: synthetic values used for offline demonstrations.
- `SCREENING`: current production path with available hazard data and documented fallback functions.
- `ENHANCED`: reserved for runs with meaningful building and financial exposure attributes.
- `PROBABILISTIC`: reserved for a future event-set and uncertainty engine.

The output includes the tier, exposure completeness, data confidence, source counts, scenario, and quality gate.

## Upgrade path

The next defensible steps are return-period flood layers, building archetypes, first-floor elevation, hazard-specific damage states, event loss curves, Monte Carlo uncertainty, and regional validation data.

## Risk layers (v1.1)

The scoring keeps these layers apart so each can be inspected and replaced.

Hazard is the site intensity (flood depth, gust, temperature, fire score, dry-spell days, landslide index) and a 0-100 hazard index, which is the damage curve evaluated at that intensity for a generic asset. Exposure is the replacement value plus a consequence factor by asset class. Vulnerability is the mean damage ratio at that intensity; for flood it uses the flood engine's return-period result (which includes first-floor height when supplied) and otherwise a generic depth curve. Risk is 100 x P(damage) x consequence factor for each hazard, and the combined score is 100 x P(any damage hazard) x consequence factor. The financial figure, `expected_loss_usd`, is a scenario loss ratio times replacement value and is reported separately from the physical score.

Per hazard and per asset the output also has a severity (Low, Medium, High, Critical), a data status (assessed, illustrative, not assessed) and a source-quality value. Missing inputs are never scored as zero: the hazard is marked not assessed and left out of the combined score, and the asset is flagged as partial.

## What is judgement, not evidence

The curve parameters (`CURVES`), the severity thresholds, the drought index scale (30 to 180 dry days mapped to 0 to 100), the consequence factors, the source-quality values and the plus or minus 15 percent sensitivity are screening assumptions chosen for transparency. None has been calibrated or validated against observed losses. The source-quality values rank sources by resolution and directness and are not probabilities. The sensitivity range is not a confidence interval.

## Reference-period and scenario handling

Baseline hazard values come from local layers or from ERA5 daily extremes for 2015-2024. Future scenarios apply fixed multipliers (temperature offset, gust factor, fire factor, sea-level rise) to those baselines; they are not CMIP6 downscaled output, and drought and landslide are not scenario-adjusted.

## Added with the API and commercial upgrade

River flood is an index hazard (Gumbel 20-year peak over median flow, scaled 2 to 20 onto 0 to 100) with no fragility curve. The `cmip6_hr` scenario applies a per-site temperature and wind delta between 1991 to 2020 and 2021 to 2050 from one model, falling back to fixed regional factors when the request fails.
