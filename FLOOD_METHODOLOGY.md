# Flood methodology, Phase 2

## Scope

This release adds a normalized flood event-loss layer while retaining the existing assessment pipeline. It is still a screening model. It does not claim parcel-level accuracy, actuarial validation, or insurance-grade results.

## Hazard inputs

The current hazard connector reads a local flood depth when available, including the Pakistan JRC 20-year return-period raster, and otherwise uses the existing source/fallback path. The flood engine requests 10, 20, 50, 100, 200, and 500 year events, but emits only return periods actually represented by source layers. It does not scale a single 20-year raster into other return periods. Unsupported tails are marked truncated. Velocity and duration remain null when the source does not provide them.

## Relative depth

If the asset has a user-supplied `first_floor_elevation_m`, the engine calculates `flood depth - FFE`. Without FFE it keeps the ground-referenced depth and labels the method. Vertical datum compatibility is not proven by the current open layers, so `vertical_datum_uncertainty` remains true.

## Vulnerability and loss

The engine assigns an explicit archetype from construction input or asset class. Until a compatible published function is selected and licensed, it uses `fallback_screening` ratios with damage states: none, slight, moderate, extensive, and complete. Structure, contents, and critical equipment losses are kept separate. Business interruption is `null` unless a supported model and financial inputs are available.

## AAL, PML, and EP

Each event stores return period, AEP, depth, relative depth, loss components, source, archetype, vulnerability type, and datum flag. AAL uses trapezoidal integration over the AEP-loss relationship with a zero-loss point at AEP 1.0. PML fields report the supported 100-year and 500-year event losses. Missing tails are marked `flood_tail_truncated`.

## Limitations

The current release does not fabricate velocity, duration, FFE, building footprints, or Pakistan-specific vulnerability observations. Shared portfolio event correlation, Monte Carlo distributions, and historical validation remain future work.
