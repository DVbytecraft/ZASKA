const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:6969/api";

export interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  error: string | null;
}

export interface CountryOption {
  code: string;
  name_en?: string;
  name_fr?: string;
  nameEn?: string;
  nameFr?: string;
  phone_prefix?: string | null;
  phonePrefix?: string | null;
  currency_code?: string | null;
  currency_symbol?: string | null;
  currencyCode?: string | null;
  currencySymbol?: string | null;
  continent_code?: string | null;
  continent_name?: string | null;
  continentCode?: string | null;
  continentName?: string | null;
  primary_city_name?: string | null;
  primaryCityName?: string | null;
  timezone?: string | null;
}

export interface CityOption {
  id: string;
  country_code: string | null;
  continent_code: string;
  code: string;
  name: string;
  slug: string;
  timezone?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_active: boolean;
  launch_status: string;
  is_primary: boolean;
}

export interface GeoSuggestion {
  label: string;
  countryCode?: string | null;
  cityName?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  source?: string;
}

export interface TargetLocationValue {
  mode: "local" | "remote";
  countryCode: string;
  cityName: string;
  address: string;
  latitude?: number | null;
  longitude?: number | null;
}

export interface FoodRestaurantSummary {
  id: string;
  publicName: string;
  description?: string | null;
  countryCode: string;
  cityName: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  currency: string;
  acceptingOrders: boolean;
  isTemporarilyClosed: boolean;
  distanceKm?: number | null;
  supportsTargetLocation?: boolean;
}

export interface FoodRestaurantDetail extends FoodRestaurantSummary {
  menus: Array<{ id: string; name: string; isDefault?: boolean }>;
  menuItems: Array<{
    id: string;
    menuId: string;
    name: string;
    description?: string | null;
    category?: string | null;
    price: string;
    currency: string;
    isAvailable: boolean;
    isSoldOut?: boolean;
  }>;
  comboOffers: Array<{
    id: string;
    name: string;
    description?: string | null;
    price: string;
    currency: string;
    items: Array<{ id: string; menuItemId: string; quantity: number }>;
  }>;
  modifiersByItem: Record<
    string,
    Array<{
      id: string;
      name: string;
      isRequired: boolean;
      minSelect?: number | null;
      maxSelect?: number | null;
      options: Array<{
        id: string;
        name: string;
        priceDelta: string;
        currency: string;
      }>;
    }>
  >;
}

export interface FoodOrderResponse {
  id: string;
  status: string;
  paymentStatus: string;
  dispatchStatus: string;
  currency: string;
  totalAmount: string;
  deliveryFee: string;
  deliveryAddress?: string | null;
  pricingBreakdown?: Record<string, unknown> | null;
  items?: Array<{ id: string; itemName: string; quantity: number; unitPrice: string; lineTotal: string }>;
}

export interface MerchantSummary {
  id: string;
  publicName: string;
  description?: string | null;
  countryCode: string;
  cityName: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  currency: string;
  acceptingOrders: boolean;
  distanceKm?: number | null;
}

export interface ShopCatalog {
  id: string;
  merchantId: string;
  name: string;
  description?: string | null;
  isActive: boolean;
}

export interface ShopItem {
  id: string;
  catalogId: string;
  merchantId?: string;
  name: string;
  description?: string | null;
  category?: string | null;
  unitPrice: string;
  currency: string;
  stockQuantity?: number | null;
  isActive: boolean;
}

export interface ShopOrderResponse {
  id: string;
  merchantId: string;
  status: string;
  paymentStatus: string;
  currency: string;
  totalAmount: string;
  deliveryAmount: string;
  deliveryAddress?: string | null;
  pricingBreakdown?: Record<string, unknown> | null;
  items?: Array<{ id: string; itemName: string; quantity: number; unitPrice: string; lineTotal: string }>;
}

export interface VtcOperatorSummary {
  id: string;
  publicName: string;
  description?: string | null;
  countryCode: string;
  cityName: string;
  currency: string;
  acceptingRides: boolean;
}

export interface VtcRideResponse {
  id: string;
  status: string;
  currency: string;
  pickupAddress: string;
  destinationAddress: string;
  estimatedFare?: string | null;
  totalFare?: string | null;
  pricingBreakdown?: Record<string, unknown> | null;
  passengerName?: string | null;
  passengerPhone?: string | null;
}

function getAccessToken() {
  return localStorage.getItem("zaska_access_token");
}

function getRefreshToken() {
  return localStorage.getItem("zaska_refresh_token");
}

function setTokens(tokens: { accessToken: string; refreshToken: string }) {
  localStorage.setItem("zaska_access_token", tokens.accessToken);
  localStorage.setItem("zaska_refresh_token", tokens.refreshToken);
}

function clearTokens() {
  localStorage.removeItem("zaska_access_token");
  localStorage.removeItem("zaska_refresh_token");
  localStorage.removeItem("zaska_user_id");
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    qs.set(key, String(value));
  });
  const raw = qs.toString();
  return raw ? `?${raw}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const accessToken = getAccessToken();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });

  if (response.status === 401 && getRefreshToken()) {
    const refreshed = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
    if (refreshed.ok) {
      const payload = (await refreshed.json()) as ApiEnvelope<{ accessToken: string; refreshToken: string }>;
      if (payload.success) {
        setTokens(payload.data);
        headers.Authorization = `Bearer ${payload.data.accessToken}`;
        response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers ?? {}) } });
      } else {
        clearTokens();
      }
    } else {
      clearTokens();
    }
  }
  return (await response.json()) as ApiEnvelope<T>;
}

export const marketplaceApi = {
  getSignupCountries: (query?: string) =>
    request<CountryOption[]>(`/auth/signup-countries${query ? buildQuery({ query }) : ""}`),

  getGeoCountries: (params?: { query?: string; signup_only?: boolean; active_only?: boolean }) =>
    request<CountryOption[]>(`/geo/countries${buildQuery(params ?? {})}`),
  getGeoCities: (params?: { country_code?: string; query?: string; active_only?: boolean }) =>
    request<CityOption[]>(`/geo/cities${buildQuery(params ?? {})}`),
  autocompletePlaces: (params: { query: string; country_code?: string; city_name?: string; limit?: number }) =>
    request<{ provider: Record<string, unknown>; results: GeoSuggestion[] }>(`/geo/places/autocomplete${buildQuery(params)}`),
  geocodePlace: (params: { address: string; country_code?: string; city_name?: string }) =>
    request<{ provider: Record<string, unknown>; result: GeoSuggestion | null }>(`/geo/places/geocode${buildQuery(params)}`),

  listFoodRestaurants: (params?: { country_code?: string; city_name?: string; reference_latitude?: number; reference_longitude?: number; limit?: number }) =>
    request<FoodRestaurantSummary[]>(`/food/restaurants${buildQuery(params ?? {})}`),
  getFoodRestaurant: (restaurantId: string) => request<FoodRestaurantDetail>(`/food/restaurants/${restaurantId}`),
  quoteFoodDelivery: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/food/quote", { method: "POST", body: JSON.stringify(payload) }),
  createFoodOrder: (payload: Record<string, unknown>) =>
    request<FoodOrderResponse>("/food/orders", { method: "POST", body: JSON.stringify(payload) }),
  fundFoodOrder: (orderId: string) =>
    request<FoodOrderResponse>(`/food/orders/${orderId}/fund`, { method: "POST", body: "{}" }),
  listMyFoodOrders: () => request<FoodOrderResponse[]>("/food/orders/me"),
  listMyRestaurantOrders: () => request<FoodOrderResponse[]>("/food/restaurant/orders"),
  updateRestaurantFoodOrderStatus: (orderId: string, status: string, estimated_prep_minutes?: number | null) =>
    request<FoodOrderResponse>(`/food/orders/${orderId}/restaurant-status`, {
      method: "POST",
      body: JSON.stringify({ status, estimated_prep_minutes }),
    }),
  listRestaurantPayouts: () => request<Record<string, unknown>[]>("/food/restaurant/payouts"),
  syncRestaurantPayouts: () => request<Record<string, unknown>>("/food/restaurant/payouts/sync", { method: "POST", body: "{}" }),

  listShopMerchants: (params?: { country_code?: string; city_name?: string; reference_latitude?: number; reference_longitude?: number; active_only?: boolean; limit?: number }) =>
    request<MerchantSummary[]>(`/shop/merchants${buildQuery(params ?? {})}`),
  listShopCatalogs: (merchantId?: string) =>
    request<ShopCatalog[]>(`/shop/catalogs${buildQuery({ merchant_id: merchantId })}`),
  listShopItems: (params?: { catalog_id?: string; merchant_id?: string; category?: string; active_only?: boolean }) =>
    request<ShopItem[]>(`/shop/items${buildQuery(params ?? {})}`),
  quoteShopDelivery: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/shop/quote", { method: "POST", body: JSON.stringify(payload) }),
  createShopOrder: (payload: Record<string, unknown>) =>
    request<ShopOrderResponse>("/shop/orders", { method: "POST", body: JSON.stringify(payload) }),
  fundShopOrder: (orderId: string) =>
    request<ShopOrderResponse>(`/shop/orders/${orderId}/fund`, { method: "POST", body: "{}" }),
  listMyShopOrders: (status?: string) => request<ShopOrderResponse[]>(`/shop/orders/me${buildQuery({ status })}`),
  listMerchantOrders: (status?: string) => request<ShopOrderResponse[]>(`/shop/merchant/orders${buildQuery({ status })}`),
  updateMerchantOrderStatus: (orderId: string, status: string, note?: string) =>
    request<ShopOrderResponse>(`/shop/merchant/orders/${orderId}/status`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),
  listMerchantPayouts: () => request<Record<string, unknown>[]>("/shop/merchant/payouts"),
  getMerchantDashboard: () => request<Record<string, unknown>>("/shop/me"),

  listVtcOperators: (params?: { country_code?: string; city_name?: string; active_only?: boolean; limit?: number }) =>
    request<VtcOperatorSummary[]>(`/vtc/operators${buildQuery(params ?? {})}`),
  quoteVtcRide: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/vtc/quote", { method: "POST", body: JSON.stringify(payload) }),
  createVtcRide: (payload: Record<string, unknown>) =>
    request<VtcRideResponse>("/vtc/rides", { method: "POST", body: JSON.stringify(payload) }),
  listMyVtcRides: (status?: string) => request<VtcRideResponse[]>(`/vtc/rides/me${buildQuery({ status })}`),
  getVtcRideDetail: (rideId: string) => request<VtcRideResponse>(`/vtc/rides/${rideId}`),
  cancelVtcRide: (rideId: string, reason?: string) =>
    request<VtcRideResponse>(`/vtc/rides/${rideId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  updateDriverPresence: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/vtc/driver/presence", { method: "POST", body: JSON.stringify(payload) }),
  updateDriverLocation: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/vtc/driver/location", { method: "POST", body: JSON.stringify(payload) }),
  listDriverOffers: () => request<Record<string, unknown>[]>("/vtc/driver/offers"),
  respondDriverOffer: (offerId: string, accept: boolean) =>
    request<Record<string, unknown>>(`/vtc/driver/offers/${offerId}/respond`, {
      method: "POST",
      body: JSON.stringify({ accept }),
    }),
  listDriverRides: () => request<VtcRideResponse[]>("/vtc/driver/rides"),
  driverRideEnRoute: (rideId: string, note?: string) =>
    request<VtcRideResponse>(`/vtc/driver/rides/${rideId}/en-route`, { method: "POST", body: JSON.stringify({ note }) }),
  driverRideArrived: (rideId: string, note?: string) =>
    request<VtcRideResponse>(`/vtc/driver/rides/${rideId}/arrived`, { method: "POST", body: JSON.stringify({ note }) }),
  driverRideStart: (rideId: string, note?: string) =>
    request<VtcRideResponse>(`/vtc/driver/rides/${rideId}/start`, { method: "POST", body: JSON.stringify({ note }) }),
  driverRideComplete: (rideId: string, payload?: Record<string, unknown>) =>
    request<VtcRideResponse>(`/vtc/driver/rides/${rideId}/complete`, { method: "POST", body: JSON.stringify(payload ?? {}) }),
  driverRideCancel: (rideId: string, note?: string) =>
    request<VtcRideResponse>(`/vtc/driver/rides/${rideId}/cancel`, { method: "POST", body: JSON.stringify({ note }) }),
  getDriverDashboard: () => request<Record<string, unknown>>("/vtc/driver/me"),
};
