import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

function fieldError(msg: string | null) {
  return msg ? <p className="text-red-500 text-xs mt-0.5">{msg}</p> : null;
}

export function CreateTaskPage() {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("XOF");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const navigate = useNavigate();

  function validate(): boolean {
    const errors: Record<string, string> = {};
    if (title.trim().length < 3) errors.title = "Le titre doit faire au moins 3 caractères.";
    if (description.trim().length < 3) errors.description = "La description doit faire au moins 3 caractères.";
    const priceNum = Number(price);
    if (!price || isNaN(priceNum) || priceNum <= 0) errors.price = "Le prix doit être un nombre positif.";
    if (currency.trim().length < 3) errors.currency = "La devise doit faire 3 caractères minimum (ex: XOF, EUR).";
    const lat = Number(latitude);
    if (isNaN(lat) || lat < -90 || lat > 90) errors.latitude = "Latitude invalide (entre -90 et 90).";
    const lon = Number(longitude);
    if (isNaN(lon) || lon < -180 || lon > 180) errors.longitude = "Longitude invalide (entre -180 et 180).";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setLoading(true);
    setError(null);
    const res = await api.createTask({
      title: title.trim(),
      description: description.trim(),
      price: Number(price),
      currency: currency.trim().toUpperCase(),
      latitude: Number(latitude),
      longitude: Number(longitude),
      status: "OPEN",
    });
    setLoading(false);
    if (!res.success) {
      setError(res.error ?? "Échec de la création");
      return;
    }
    navigate(`/tasks/${(res.data as { id: string }).id}`);
  }

  return (
    <div className="space-y-4 max-w-lg">
      <h2 className="text-xl font-semibold">Créer une tâche</h2>

      <div>
        <label className="block text-sm font-medium mb-1">Titre *</label>
        <input
          className="w-full border p-2 rounded"
          placeholder="Ex: Livraison de colis à Dakar"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        {fieldError(fieldErrors.title ?? null)}
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Description *</label>
        <textarea
          className="w-full border p-2 rounded"
          rows={3}
          placeholder="Décrivez la tâche en détail..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        {fieldError(fieldErrors.description ?? null)}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Prix *</label>
          <input
            className="w-full border p-2 rounded"
            type="number"
            min="0"
            step="0.01"
            placeholder="5000"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
          {fieldError(fieldErrors.price ?? null)}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Devise *</label>
          <select className="w-full border p-2 rounded" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option value="XOF">XOF (FCFA)</option>
            <option value="EUR">EUR</option>
            <option value="USD">USD</option>
            <option value="GHS">GHS</option>
            <option value="NGN">NGN</option>
          </select>
          {fieldError(fieldErrors.currency ?? null)}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium mb-1">Latitude *</label>
          <input
            className="w-full border p-2 rounded"
            placeholder="14.7167"
            value={latitude}
            onChange={(e) => setLatitude(e.target.value)}
          />
          {fieldError(fieldErrors.latitude ?? null)}
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Longitude *</label>
          <input
            className="w-full border p-2 rounded"
            placeholder="-17.4677"
            value={longitude}
            onChange={(e) => setLongitude(e.target.value)}
          />
          {fieldError(fieldErrors.longitude ?? null)}
        </div>
      </div>

      {error ? <p className="text-red-600 text-sm">{error}</p> : null}

      <button
        className="bg-black text-white rounded px-4 py-2 disabled:opacity-50 w-full"
        disabled={loading}
        onClick={handleSubmit}
      >
        {loading ? "Création en cours..." : "Créer la tâche"}
      </button>
    </div>
  );
}
