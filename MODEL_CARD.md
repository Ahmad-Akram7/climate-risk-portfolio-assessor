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
