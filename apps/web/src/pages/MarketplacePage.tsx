import { Link } from "react-router-dom";
import { TargetLocationPicker } from "../components/TargetLocationPicker";
import { useAuthStore } from "../store";

const customerModules = [
  {
    to: "/food",
    title: "Commander à manger",
    eyebrow: "Local & distance",
    description:
      "Repérez les restaurants autour de vous ou autour d’un proche dans le pays, la ville et la zone ciblés.",
  },
  {
    to: "/shop",
    title: "Acheter des articles",
    eyebrow: "Local & distance",
    description:
      "Parcourez les vendeurs et produits proches de l’adresse ciblée pour acheter pour vous ou pour quelqu’un d’autre.",
  },
  {
    to: "/vtc",
    title: "Réserver un VTC",
    eyebrow: "Mobilité",
    description:
      "Calculez un tarif clair et déclenchez une course locale ou à distance pour un passager ciblé.",
  },
  {
    to: "/tasks/new",
    title: "Publier une tâche",
    eyebrow: "Services",
    description:
      "Publiez un besoin, recevez des réponses de taskers proches et négociez le bon prix si nécessaire.",
  },
];

const partnerModules = [
  {
    to: "/food/partner",
    title: "Espace restaurant",
    description: "Commandes, préparation, statuts et paiements restaurant.",
  },
  {
    to: "/shop/partner",
    title: "Espace vendeur",
    description: "Catalogue, fulfilment, commandes et payouts marchand.",
  },
  {
    to: "/vtc/driver",
    title: "Espace chauffeur",
    description: "Présence, offres, courses et clôture opérationnelle.",
  },
];

export function MarketplacePage() {
  const profile = useAuthStore((s) => s.profile);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold text-gray-900">Explorer Zaska</h2>
        <p className="mt-1 text-sm text-gray-500">
          Choisissez d’abord la zone ciblée, puis lancez la bonne action : locale ou à distance, client ou partenaire.
        </p>
      </div>

      <div className="overflow-hidden rounded-3xl bg-gradient-to-r from-gray-950 via-black to-gray-800 p-6 text-white">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-3">
            <p className="text-xs uppercase tracking-[0.24em] text-gray-300">Commande intelligente</p>
            <h3 className="text-3xl font-bold leading-tight">
              Depuis une seule entrée, vous pouvez commander pour vous ou pour quelqu’un, partout où Zaska est actif.
            </h3>
            <p className="text-sm text-gray-300">
              Commencez par le pays, la ville, le quartier ou l’adresse cible. Ensuite, le système vous oriente
              vers les restaurants, vendeurs, chauffeurs ou taskers les plus pertinents.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-gray-200">
            <p className="font-semibold text-white">Règle produit</p>
            <p className="mt-2">
              Ce que l’utilisateur voit en priorité doit venir de son pays, de sa ville et de sa zone — sauf s’il
              choisit explicitement une cible distante.
            </p>
          </div>
        </div>
      </div>

      <TargetLocationPicker
        storageKey="zaska-marketplace-target"
        defaultCountryCode={profile?.country_code}
        title="Quelle zone souhaitez-vous cibler ?"
        description="Fixez la cible une bonne fois : pays, ville et adresse. Cette logique sert ensuite de point de départ pour vos commandes locales ou à distance."
      />

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Modules côté client</h3>
            <p className="mt-1 text-sm text-gray-500">
              Même expérience de ciblage, puis un parcours spécifique selon le type de besoin.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {customerModules.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="rounded-2xl border border-gray-200 bg-white p-5 transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{item.eyebrow}</p>
                <h4 className="mt-2 text-lg font-semibold text-gray-900">{item.title}</h4>
                <p className="mt-2 text-sm text-gray-500">{item.description}</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Modules côté opérateur</h3>
            <p className="mt-1 text-sm text-gray-500">
              Chaque partenaire dispose d’une interface dédiée, jamais confondue avec celle du client.
            </p>
          </div>
          <div className="space-y-3">
            {partnerModules.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="block rounded-2xl border border-gray-200 bg-gray-50 p-4 transition hover:bg-white hover:shadow-sm"
              >
                <h4 className="font-semibold text-gray-900">{item.title}</h4>
                <p className="mt-2 text-sm text-gray-500">{item.description}</p>
              </Link>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-gray-200 bg-white p-5">
        <h3 className="text-lg font-semibold text-gray-900">Exemples d’usage bien couverts</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-rose-100 bg-rose-50 p-4">
            <p className="text-sm font-semibold text-rose-700">Food diaspora</p>
            <p className="mt-2 text-sm text-rose-900">
              Je suis à Lomé et je commande un repas à Paris pour ma compagne, en ciblant sa ville et son adresse.
            </p>
          </div>
          <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4">
            <p className="text-sm font-semibold text-indigo-700">Articles ciblés</p>
            <p className="mt-2 text-sm text-indigo-900">
              Je filtre le pays et la ville d’un proche pour acheter un article local auprès d’un vendeur proche.
            </p>
          </div>
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
            <p className="text-sm font-semibold text-emerald-700">VTC à distance</p>
            <p className="mt-2 text-sm text-emerald-900">
              Je demande une course pour quelqu’un d’autre dans un autre pays et je renseigne son identité côté passager.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
