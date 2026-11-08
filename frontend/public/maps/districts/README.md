# Congressional district boundaries
Source: U.S. Census Bureau, 2024 cartographic boundary files for the 119th Congress.
https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_cd119_500k.zip

Public-domain geographic data. These maps cover the 50 states and 435 voting districts.
District 0 is at-large. The geometry is simplified for display, not address lookup.
Alaska longitudes are unwrapped across the antimeridian. Each state uses a local equirectangular projection.

To regenerate, download and extract the archive, then run from frontend:
    node scripts/build-district-maps.mjs <extracted-directory>

The generator validates 50 states, 435 districts, nonempty paths and a 150 KB limit per state.
Update the source, district field and Congress label when adopting new congressional boundaries.
Historical votes retain their backend records; these maps do not depict historical boundaries.
