# Physical Climate Risk Assessment

*Scenario: Current climate - generated 2026-10-08*

## 1. Executive summary

The portfolio contains 5 assets with a total replacement value of $300.0M. Modelled scenario expected loss is $30.6M (10.19% of value). The value-weighted risk score is 27.4/100. 0 asset(s) are rated Critical, 0 High, 2 Medium and 3 Low.

Hazard inputs are predominantly real data (confidence 1.00).

## 2. Methodology and data sources

Assets are validated and spatially quality-checked, then hazard intensities are attached for flood, wind, wildfire, extreme heat and elevation. Intensities are converted to damage probabilities with sigmoid fragility curves, combined across hazards with a survival model, and multiplied by an asset-class criticality factor. Expected loss is probability x loss ratio x replacement value.

- flood: JRC_RP20Y_NoMappedDepth_Local (5 assets)
- wind: OpenMeteo_ERA5_API (5 assets)
- heat: NOAA_CDO_API (5 assets)
- wildfire: Pakistan_Wildfire_Susceptibility_2023_P90_NoData (5 assets)
- elevation: OpenTopography_COP30_API (5 assets)

## 3. Material risk findings

Average damage probability by hazard: wind 14.3%, heat 4.9%, flood 0.0%, wildfire 0.0%.

Geographic concentration: FL 56.7% of value, CO 26.7% of value, CA 10.0% of value.

Highest-risk assets:

- Miami Hospital (TEST-FL-002, FL, hospital): score 44.1, Medium, driven by wind, modelled loss $21.1M.
- Miami Coastal Office (TEST-FL-001, FL, office): score 33.5, Medium, driven by wind, modelled loss $6.7M.
- Los Angeles Office (TEST-CA-001, CA, office): score 23.9, Low, driven by heat, modelled loss $805,613.

## 4. Recommended mitigation strategies

The most common dominant hazard is wind: upgrade roof and envelope connections, shutters/impact glazing, and wind-rated rooftop equipment. Prioritise Critical and High tier assets and reassess after mitigation.

## 5. Framework alignment

- SEC: SEC climate-related disclosure (Regulation S-K style: material physical risks, location/concentration, financial impact).
- CSRD: EU CSRD / ESRS E1 (physical risk exposure by hazard, asset-level analysis, scenario analysis).
- ISSB: ISSB IFRS S2 (climate-related physical risks, scenario analysis, financial effects).

## 6. Limitations and caveats

Fragility parameters are uncalibrated defaults; the loss figure is scenario-based, not annual expected loss. Coordinates are treated as points; building-level attributes (age, construction, floor height) are not used. Future scenarios apply simple parametric uplifts rather than downscaled climate-model output. Regulatory requirements change; confirm current applicability of each framework with counsel.

> This report is an automated screening-level assessment generated from the supplied asset list. It is not an engineering study, actuarial valuation, or legal/regulatory advice. Review by qualified professionals is required before any external disclosure.