import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store";

type Mode = "login" | "register" | "verify";

const STEPS: Record<Exclude<Mode, "login">, number> = {
  register: 1,
  verify: 2,
};

export function AuthPage() {
  const [mode, setMode] = useState<Mode>("login");

  // Login
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Register
  const [regEmail, setRegEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [role, setRole] = useState("client");

  // OTP (mode normal sans bypass)
  const [otp, setOtp] = useState("");

  const { login, register, verifyOtp, loading, error } = useAuthStore();
  const navigate = useNavigate();

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
    Object.values(passwordRules).every(Boolean);

  const handleRegister = async () => {
    const out = await register({
      email: regEmail.toLowerCase().trim(),
      firstName: firstName.trim(),
      lastName: lastName.trim(),
      phone: phone.trim(),
      role,
      password: regPassword,
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
    setFirstName(""); setLastName(""); setPhone(""); setRegEmail(""); setRegPassword(""); setRole("client"); setOtp("");
    setMode("register");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-sm p-8 space-y-6">

        <div className="text-center">
          <span className="text-3xl font-black tracking-tight text-gray-900">ZASKA</span>
          <p className="text-sm text-gray-500 mt-1">
            {mode === "login" && "Connectez-vous à votre compte"}
            {mode === "register" && "Créer un compte — Étape 1/2"}
            {mode === "verify" && "Vérification email — Étape 2/2"}
          </p>
        </div>

        {mode !== "login" && (
          <div className="flex gap-1">
            {[1, 2].map((s) => (
              <div
                key={s}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  s <= STEPS[mode as Exclude<Mode, "login">] ? "bg-gray-900" : "bg-gray-200"
                }`}
              />
            ))}
          </div>
        )}

        <div className="space-y-3">
          {/* LOGIN */}
          {mode === "login" && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <input
                  type="email"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  placeholder="votre@email.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Mot de passe</label>
                <input
                  type="password"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </>
          )}

          {/* REGISTER */}
          {mode === "register" && (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Prénom</label>
                  <input
                    type="text"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                    placeholder="Jean"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Nom</label>
                  <input
                    type="text"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                    placeholder="Dupont"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <input
                  type="email"
                  className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 ${
                    regEmail && !emailValid ? "border-red-300" : "border-gray-200"
                  }`}
                  placeholder="votre@email.com"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                />
                {regEmail && !emailValid && (
                  <p className="text-xs text-red-500 mt-1">Email invalide</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Téléphone</label>
                <input
                  type="tel"
                  className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 ${
                    phone && !phoneValid ? "border-red-300" : "border-gray-200"
                  }`}
                  placeholder="+228 90 00 00 00"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                {phone && !phoneValid && (
                  <p className="text-xs text-red-500 mt-1">Numéro invalide</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Mot de passe</label>
                <input
                  type="password"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  placeholder="••••••••"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                />
                {regPassword && (
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
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Je suis</label>
                <select
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                >
                  <option value="client">Client — je cherche un prestataire</option>
                  <option value="tasker">Tasker — je propose mes services</option>
                </select>
              </div>
            </>
          )}

          {/* VERIFY (mode OTP email — désactivé si bypass actif) */}
          {mode === "verify" && (
            <div>
              <p className="text-sm text-gray-500 text-center mb-3">
                Code envoyé à <span className="font-semibold text-gray-900">{regEmail}</span>
              </p>
              <label className="block text-xs font-medium text-gray-600 mb-1">Code de vérification</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm tracking-widest text-center font-mono focus:outline-none focus:ring-2 focus:ring-gray-900"
                placeholder="• • • • • •"
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
              />
            </div>
          )}
        </div>

        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}

        <button
          className="w-full bg-gray-900 text-white rounded-xl py-3 text-sm font-semibold disabled:opacity-40 transition-opacity"
          disabled={
            loading ||
            (mode === "register" && !registerValid) ||
            (mode === "verify" && otp.length < 6)
          }
          onClick={
            mode === "login" ? handleLogin
            : mode === "register" ? handleRegister
            : handleVerify
          }
        >
          {loading ? "Chargement..." :
            mode === "login" ? "Se connecter" :
            mode === "register" ? "Créer mon compte" :
            "Vérifier mon email"}
        </button>

        <p className="text-center text-xs text-gray-500">
          {mode === "login" ? (
            <>Pas encore de compte ?{" "}
              <button className="font-semibold text-gray-900 underline" onClick={() => setMode("register")}>
                S'inscrire
              </button>
            </>
          ) : (
            <>Déjà un compte ?{" "}
              <button className="font-semibold text-gray-900 underline" onClick={() => setMode("login")}>
                Se connecter
              </button>
            </>
          )}
          {mode === "verify" && (
            <><br />
              <button className="font-semibold text-gray-900 underline mt-1" onClick={resetRegister}>
                Modifier l'email
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
