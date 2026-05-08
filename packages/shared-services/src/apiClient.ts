interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  error: string | null;
}

type TokenStore = {
  accessToken: string | null;
  refreshToken: string | null;
};

type SessionMeta = {
  countryCode: string | null;
  currency: string | null;
  userId: string | null;
};

const inMemoryTokens: TokenStore = { accessToken: null, refreshToken: null };
const inMemoryMeta: SessionMeta = { countryCode: null, currency: null, userId: null };

type _ViteImportMeta = { env?: Record<string, string | undefined> };

function resolveBaseUrl() {
  if (typeof import.meta !== "undefined") {
    const url = (import.meta as _ViteImportMeta).env?.VITE_API_URL;
    if (url) return url;
  }
  if (typeof process !== "undefined" && process.env?.ZASKA_API_BASE_URL) {
    return process.env.ZASKA_API_BASE_URL;
  }
  return "http://localhost:6969/api";
}

const defaultBaseUrl = resolveBaseUrl();

async function unwrap<T>(response: Response): Promise<T> {
  const json = (await response.json()) as ApiEnvelope<T> | T;
  if (
    json !== null &&
    typeof json === "object" &&
    "success" in (json as object) &&
    "data" in (json as object)
  ) {
    const envelope = json as ApiEnvelope<T>;
    if (!envelope.success) {
      throw new Error(envelope.error ?? "API error");
    }
    return envelope.data;
  }
  return json as T;
}

export class ApiClient {
  constructor(private readonly baseUrl = defaultBaseUrl) {}

  setTokens(tokens: Partial<TokenStore>) {
    inMemoryTokens.accessToken = tokens.accessToken ?? inMemoryTokens.accessToken;
    inMemoryTokens.refreshToken = tokens.refreshToken ?? inMemoryTokens.refreshToken;
  }

  setCountry(countryCode: string | null | undefined, currency?: string | null) {
    if (countryCode) inMemoryMeta.countryCode = countryCode.toUpperCase();
    if (currency) inMemoryMeta.currency = currency.toUpperCase();
  }

  setUserId(userId: string | null) {
    inMemoryMeta.userId = userId;
  }

  clearTokens() {
    inMemoryTokens.accessToken = null;
    inMemoryTokens.refreshToken = null;
    inMemoryMeta.countryCode = null;
    inMemoryMeta.currency = null;
    inMemoryMeta.userId = null;
  }

  getAccessToken() { return inMemoryTokens.accessToken; }
  getRefreshToken() { return inMemoryTokens.refreshToken; }
  getCountryCode() { return inMemoryMeta.countryCode; }
  getCurrency() { return inMemoryMeta.currency; }
  getUserId() { return inMemoryMeta.userId; }

  async get<T>(path: string): Promise<T> {
    let response = await fetch(`${this.baseUrl}${path}`, {
      headers: this.authHeaders(),
    });
    if (response.status === 401 && (await this.tryRefresh())) {
      response = await fetch(`${this.baseUrl}${path}`, { headers: this.authHeaders() });
    }
    if (!response.ok) throw new Error(await this.extractError(response, `GET ${path} failed: ${response.status}`));
    return unwrap<T>(response);
  }

  async post<T>(path: string, body: unknown, extraHeaders?: Record<string, string>): Promise<T> {
    const buildHeaders = () => ({
      "Content-Type": "application/json",
      ...this.authHeaders(),
      ...extraHeaders,
    });
    let response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(body),
    });
    if (response.status === 401 && (await this.tryRefresh())) {
      response = await fetch(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify(body),
      });
    }
    if (!response.ok) throw new Error(await this.extractError(response, `POST ${path} failed: ${response.status}`));
    return unwrap<T>(response);
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    let response = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...this.authHeaders() },
      body: JSON.stringify(body),
    });
    if (response.status === 401 && (await this.tryRefresh())) {
      response = await fetch(`${this.baseUrl}${path}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...this.authHeaders() },
        body: JSON.stringify(body),
      });
    }
    if (!response.ok) throw new Error(await this.extractError(response, `PATCH ${path} failed: ${response.status}`));
    return unwrap<T>(response);
  }

  async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: this.authHeaders(),
    });
    if (!response.ok) throw new Error(await this.extractError(response, `DELETE ${path} failed: ${response.status}`));
    return unwrap<T>(response);
  }

  private async extractError(response: Response, fallback: string): Promise<string> {
    try {
      const body = (await response.json()) as ApiEnvelope<unknown>;
      if (body?.error) return body.error;
    } catch {
      // ignore JSON parse errors
    }
    return fallback;
  }

  private authHeaders(): Record<string, string> {
    if (!inMemoryTokens.accessToken) return {};
    return { Authorization: `Bearer ${inMemoryTokens.accessToken}` };
  }

  private async tryRefresh(): Promise<boolean> {
    if (!inMemoryTokens.refreshToken) return false;
    const response = await fetch(`${this.baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: inMemoryTokens.refreshToken }),
    });
    if (!response.ok) return false;
    try {
      const data = await unwrap<{ accessToken: string; refreshToken: string }>(response);
      this.setTokens(data);
      return true;
    } catch {
      return false;
    }
  }
}

export const apiClient = new ApiClient();
