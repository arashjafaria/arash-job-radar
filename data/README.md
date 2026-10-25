# German place lookup

`german_places.json.gz` is derived from GeoNames' German country dump:
https://download.geonames.org/export/dump/DE.zip (downloaded 2026-10-23).

Attribution: GeoNames, https://www.geonames.org/, licensed under
Creative Commons Attribution 4.0: https://creativecommons.org/licenses/by/4.0/.
This derived work filters German populated places and municipalities, normalizes
Latin spelling variants, and precomputes membership in a 150 km great-circle
radius from Munich (48.1351253, 11.5819805). Nuremberg is an explicit exception.
The archive's SHA-256, parameters and record count are embedded in the data.

Rebuild explicitly with `python -m scripts.build_city_lookup /path/to/DE.zip`.
This uses Python's standard library only. Normal scans load the compressed file
once and perform local name/state lookups; no coordinates are recalculated and
no geocoder/network service is called. Distances are straight-line, not driving.

Coverage: 92,966 populated-place/municipality records and 111,460 normalized
name variants. Historical/abandoned/destroyed populated places are excluded.
GeoNames is community maintained, so coverage and coordinates are not guaranteed
complete. Unknown names and ambiguous names spanning both radius outcomes go to
manual review. Identically named minor settlements do not override a dominant
city (population at least 20,000 and ten times the next candidate). State names
can disambiguate candidates. The runtime never accepts an unknown name solely
because LinkedIn returned it from a radius search.

Runtime policy additionally excludes Geislingen an der Steige and Leonberg
from onsite delivery at the user's request (2026-10-25). These explicit overrides
do not alter the precomputed data. Unresolved places stay in an internal hold;
they are not sent to Telegram as manual-review opportunities.
