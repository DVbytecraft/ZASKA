import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { marketplaceApi, type CountryOption } from "../services/marketplaceApi";
import { useAuthStore } from "../store";

type Mode = "login" | "register" | "verify";

const STEPS: Record<Exclude<Mode, "login">, number> = {
  register: 1,
  verify: 2,
};

export function AuthPage() {
  const [mode, setMode] = useState<Mode>("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [regEmail, setRegEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [role, setRole] = useState("client");
  const [country, setCountry] = useState("");
  const [countryQuery, setCountryQuery] = useState("");
  const [countries, setCountries] = useState<CountryOption[]>([]);
  const [countriesLoading, setCountriesLoading] = useState(false);
  const [countriesError, setCountriesError] = useState<string | null>(null);

  const [otp, setOtp] = useState("");

  const { login, register, verifyOtp, loading, error } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    if (mode !== "register") return;
    let active = true;

    const loadCountries = async () => {
      setCountriesLoading(true);
      setCountriesError(null);
      const res = await marketplaceApi.getSignupCountries(countryQuery.trim() || undefined);
      if (!active) return;
      setCountriesLoading(false);
      if (!res.success) {
        setCountriesError(res.error ?? "Impossible de charger les pays couverts.");
        return;
      }
      setCountries(res.data);
      setCountry((current) => {
        if (current && res.data.some((item) => item.code === current)) {
          return current;
        }
        return res.data[0]?.code ?? "";
      });
    };

    void loadCountries();

    return () => {
      active = false;
    };
  }, [mode, countryQuery]);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(regEmail);
  const passwordRules = {
    length: regPassword.length >= 8,
    upper: /[A-Z]/.test(regPassword),
    digit: /\d/.test(regPassword),
  };
  const phoneValid = /^\+?[0-9]{7,15}$/.test(phone.trim());
  const registerValid =
    firstName.trim().length >= 2 &&
    lastName.trim().length >= 2 &&
    phoneValid &&
    emailValid &&
    country.trim().length >= 2 &&
    Object.values(passwordRules).every(Boolean);

  const selectedCountry = useMemo(
    () => countries.find((item) => item.code === country) ?? null,
    [countries, country],
  );

  const handleRegister = async () => {
    const out = await register({
      email: regEmail.toLowerCase().trim(),
      firstName: firstName.trim(),
      lastName: lastName.trim(),
      phone: phone.trim(),
      role,
      password: regPassword,
      country,
    });
    if (!out.ok) return;
    setMode("verify");
  };

  const handleVerify = async () => {
    const ok = await verifyOtp(regEmail.toLowerCase().trim(), otp);
    if (ok) navigate("/");
  };

  const handleLogin = async () => {
    const ok = await login(email, password);
    if (ok) navigate("/");
  };

  const resetRegister = () => {
    setFirstName("");
    setLastName("");
    setPhone("");
    setRegEmail("");
    setRegPassword("");
    setRole("client");
    setOtp("");
    setCountry(countries[0]?.code ?? "");
    setMode("register");
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-6xl overflow-hidden rounded-3xl border bg-white shadow-xl">
        <div className="hidden w-1/2 bg-gray-950 p-10 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="space-y-6">
            <div>
              <span className="text-3xl font-black tracking-tight">ZASKA</span>
              <p className="mt-3 max-w-md text-sm text-gray-300">
                Une plateforme pensée pour les services locaux, la commande à distance et les opérations
                partenaires, ville par ville.
              </p>
            </div>
            <div className="grid gap-4">
              {[
                {
                  title: "Commander localement ou à distance",
                  body: "Choisissez votre propre zone ou ciblez le pays et la ville d’un proche avant de commander.",
                },
                {
                  title: "Des modules activés selon le pays",
                  body: "Seuls les pays réellement couverts sont proposés à l’inscription pour éviter les faux départs.",
                },
                {
                  title: "Une expérience double face",
                  body: "Clients, taskers, restaurants, marchands et chauffeurs disposent chacun de leur cockpit dédié.",
                },
              ].map((item) => (
                <div key={item.title} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <h3 className="text-sm font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm text-gray-300">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
          <p className="text-xs text-gray-400">
            Nous affichons prioritairement ce qui est pertinent pour votre pays, votre ville et votre zone.
          </p>
        </div>

        <div className="w-full p-8 lg:w-1/2">
          <div className="mx-auto w-full max-w-md space-y-6">
            <div className="text-center">
              <span className="text-3xl font-black tracking-tight text-gray-900">ZASKA</span>
              <p className="mt-1 text-sm text-gray-500">
                {mode === "login" && "Connectez-vous à votre compte"}
                {mode === "register" && "Créer un compte — Étape 1/2"}
                {mode === "verify" && "Vérification email — Étape 2/2"}
              </p>
            </div>

            {mode !== "login" ? (
              <div className="flex gap-1">
                {[1, 2].map((step) => (
                  <div
                    key={step}
                    className={`h-1 flex-1 rounded-full transition-colors ${
                      step <= STEPS[mode as Exclude<Mode, "login">] ? "bg-gray-900" : "bg-gray-200"
                    }`}
                  />
                ))}
              </div>
            ) : null}

            <div className="space-y-3">
              {mode === "login" ? (
                <>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-600">Email</label>
                    <input
                      type="email"
                      className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                      placeholder="votre@email.com"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-600">Mot de passe</label>
                    <input
                      type="password"
                      className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                      placeholder="••••••••"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  </div>
                </>
              ) : null}

              {mode === "register" ? (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-gray-600">Prénom</label>
                      <input
                        type="text"
                        className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                        placeholder="Jean"
                        value={firstName}
                        onChange={(event) => setFirstName(event.target.value)}
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-gray-600">Nom</label>
                      <input
                        type="text"
                        className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                        placeholder="Dupont"
                        value={lastName}
                        onChange={(event) => setLastName(event.target.value)}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-600">Email</label>
                    <input
                      type="email"
                      className={`w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 ${
                        regEmail && !emailValid ? "border-red-300" : "border-gray-200"
                      }`}
                      placeholder="votre@email.com"
                      value={regEmail}
                      onChange={(event) => setRegEmail(event.target.value)}
                    />
                    {regEmail && !emailValid ? <p className="mt-1 text-xs text-red-500">Email invalide</p> : null}
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-600">Téléphone</label>
                    <input
                      type="tel"
                      className={`w-full rounded-lg border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 ${
                        phone && !phoneValid ? "border-red-300" : "border-gray-200"
                      }`}
                      placeholder="+22890000000"
                      value={phone}
                      onChange={(event) => setPhone(event.target.value)}
                    />
                    {phone && !phoneValid ? <p className="mt-1 text-xs text-red-500">Numéro invalide</p> : null}
                  </div>

                  <div className="space-y-2 rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <label className="block text-xs font-medium text-gray-700">Pays couvert</label>
                      <span className="text-[11px] text-gray-400">
                        Si votre pays n’apparaît pas, Zaska n’y opère pas encore.
                      </span>
                    </div>
                    <input
                      type="text"
                      className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                      placeholder="Rechercher un pays couvert"
                      value={countryQuery}
                      onChange={(event) => setCountryQuery(event.target.value)}
                    />
                    <select
                      className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                      value={country}
                      onChange={(event) => setCountry(event.target.value)}
                      disabled={countriesLoading || countries.length === 0}
                    >
                      {countries.length === 0 ? (
                        <option value="">
                          {countriesLoading ? "Chargement des pays..." : "Aucun pays couvert disponible"}
                        </option>
                      ) : (
                        countries.map((item) => (
                          <option key={item.code} value={item.code}>
                            {item.nameFr ?? item.name_fr ?? item.nameEn ?? item.name_en ?? item.code} ({item.code})
                          </option>
                        ))
                      )}
                    </select>
                    {selectedCountry ? (
                      <p className="text-xs text-gray-500">
                        {selectedCountry.continentName ?? selectedCountry.continent_name ?? "Région active"} · Devise{" "}
                        {selectedCountry.currencyCode ?? selectedCountry.currency_code ?? "--"} · Ville pivot{" "}
                        {selectedCountry.primaryCityName ?? selectedCountry.primary_city_name ?? "—"}
                      </p>
                    ) : null}
                    {countriesError ? <p className="text-xs text-red-500">{countriesError}</p> : null}
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-600">Mot de passe</label>
                    <input
                      type="password"
                      className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                      placeholder="••••••••"
                      value={regPassword}
                      onChange={(event) => setRegPassword(event.target.value)}
                    />
                    {regPassword ? (
                      <div className="mt-1.5 grid grid-cols-2 gap-0.5">
                        {[
                          { ok: passwordRules.length, label: "8 caractères min" },
                          { ok: passwordRules.upper, label: "1 majuscule" },
                          { ok: passwordRules.digit, label: "1 chiffre" },
                        ].map(({ ok, label }) => (
                          <span key={label} className={`text-xs ${ok ? "text-green-600" : "text-gray-400"}`}>
                            {ok ? "✓" : "·"} {label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-600">Je suis</label>
                    <select
                      className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                      value={role}
                      onChange={(event) => setRole(event.target.value)}
                    >
                      <option value="client">Client — je cherche un prestataire ou je commande</option>
                      <option value="tasker">Tasker — je propose mes services</option>
                    </select>
                  </div>
                </>
              ) : null}

              {mode === "verify" ? (
                <div>
                  <p className="mb-3 text-center text-sm text-gray-500">
                    Code envoyé à <span className="font-semibold text-gray-900">{regEmail}</span>
                  </p>
                  <label className="mb-1 block text-xs font-medium text-gray-600">Code de vérification</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-center font-mono text-sm tracking-widest focus:outline-none focus:ring-2 focus:ring-gray-900"
                    placeholder="• • • • • •"
                    value={otp}
                    onChange={(event) => setOtp(event.target.value.replace(/\D/g, ""))}
                  />
                </div>
              ) : null}
            </div>

            {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p> : null}

            <button
              className="w-full rounded-xl bg-gray-900 py-3 text-sm font-semibold text-white transition-opacity disabled:opacity-40"
              disabled={
                loading ||
                (mode === "register" && !registerValid) ||
                (mode === "verify" && otp.length < 6)
              }
              onClick={mode === "login" ? handleLogin : mode === "register" ? handleRegister : handleVerify}
            >
              {loading
                ? "Chargement..."
                : mode === "login"
                  ? "Se connecter"
                  : mode === "register"
                    ? "Créer mon compte"
                    : "Vérifier mon email"}
            </button>

            <p className="text-center text-xs text-gray-500">
              {mode === "login" ? (
                <>
                  Pas encore de compte ?{" "}
                  <button className="font-semibold text-gray-900 underline" onClick={() => setMode("register")}>
                    S&apos;inscrire
                  </button>
                </>
              ) : (
                <>
                  Déjà un compte ?{" "}
                  <button className="font-semibold text-gray-900 underline" onClick={() => setMode("login")}>
                    Se connecter
                  </button>
                </>
              )}
              {mode === "verify" ? (
                <>
                  <br />
                  <button className="mt-1 font-semibold text-gray-900 underline" onClick={resetRegister}>
                    Modifier l&apos;email
                  </button>
                </>
              ) : null}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
