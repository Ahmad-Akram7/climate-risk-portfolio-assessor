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
