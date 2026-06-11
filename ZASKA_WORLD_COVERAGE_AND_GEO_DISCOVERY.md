# ZASKA World Coverage and Geo Discovery

## Backend delivered in this lot

- Global world-country reference catalog backed by `backend/fastapi/app/core/world_countries_timezones.raw.json`
- Runtime catalog loader in `backend/fastapi/app/core/world_country_catalog.py`
- Country rollout upgraded to seed all countries, while keeping only launch-ready countries active by default
- Signup restricted to active countries only through `CountryRolloutService.assert_country_signup_open()`
- Public signup-country endpoint: `GET /api/auth/signup-countries`
- Public geo endpoints:
  - `GET /api/geo/countries`
  - `GET /api/geo/cities`
  - `GET /api/geo/places/autocomplete`
  - `GET /api/geo/places/geocode`
- Provider-agnostic maps abstraction in `backend/fastapi/app/services/maps_service.py`
- Cross-border discovery improvements:
  - `GET /api/food/restaurants` now accepts target country/city and reference coordinates
  - `GET /api/shop/merchants` added for target-country/target-city commerce discovery
  - `GET /api/vtc/operators` now supports softer city filtering and explicit result limiting

## Product behavior now enforced

- A country can exist in the platform catalog without being open for signup or operations.
- Users cannot sign up with a country that is not active and signup-enabled.
- Admin still keeps full control of activation through rollout and country-management interfaces.
- Discovery can now be based on the beneficiary's target country, city, and nearby coordinates instead of the buyer's current location.

## Architecture note

- Maps support is backend-first and provider-agnostic.
- `mock` mode works from local country/city catalogs.
- `google` and `mapbox` can be enabled later through environment variables without redesigning the API surface.
