import { useEffect, useState, useMemo, type ComponentType } from 'react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell
} from 'recharts';
import { TrendingUp, Users, Briefcase, DollarSign, RefreshCw, Loader2 } from 'lucide-react';
import { adminApi, type AdminStats, type AdminTransaction, type AdminTask, type AdminUser } from '../adminApi';

// ─── Data builders (real data only — no fake fallbacks) ───────────────────────

function buildRevenueData(transactions: AdminTransaction[]) {
  const byMonth: Record<string, { revenue: number; count: number }> = {};
  for (const tx of transactions) {
    if (tx.status !== 'completed') continue;
    const d = new Date(tx.created_at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!byMonth[key]) byMonth[key] = { revenue: 0, count: 0 };
    byMonth[key].revenue += Number(tx.amount);
    byMonth[key].count += 1;
  }
  return Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-6)
    .map(([key, v]) => ({
      month: key.slice(5) + '/' + key.slice(2, 4),
      revenue: v.revenue,
      transactions: v.count,
    }));
}

function buildUserGrowthData(users: AdminUser[]) {
  const byMonth: Record<string, { clients: number; taskers: number }> = {};
  for (const u of users) {
    const d = new Date(u.created_at);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!byMonth[key]) byMonth[key] = { clients: 0, taskers: 0 };
    if (u.role === 'client') byMonth[key].clients++;
    else if (u.role === 'tasker') byMonth[key].taskers++;
  }
  let cumC = 0; let cumT = 0;
  return Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-6)
    .map(([key, v]) => {
      cumC += v.clients; cumT += v.taskers;
      return { month: key.slice(5) + '/' + key.slice(2, 4), clients: cumC, taskers: cumT };
    });
}

function buildTaskFunnelData(tasks: AdminTask[]) {
  const total = tasks.length;
  const assigned = tasks.filter(t => ['ASSIGNED', 'IN_PROGRESS', 'COMPLETED'].includes(t.status)).length;
  const inProgress = tasks.filter(t => t.status === 'IN_PROGRESS' || t.status === 'COMPLETED').length;
  const completed = tasks.filter(t => t.status === 'COMPLETED').length;
  return [
    { label: 'Créées', value: total, fill: '#6D28D9' },
    { label: 'Assignées', value: assigned, fill: '#7C3AED' },
    { label: 'En cours', value: inProgress, fill: '#8B5CF6' },
    { label: 'Terminées', value: completed, fill: '#A78BFA' },
  ];
}

function buildGeoData(users: AdminUser[]) {
  const byCo: Record<string, number> = {};
  for (const u of users) {
    const c = u.country_code ?? 'XX';
    byCo[c] = (byCo[c] ?? 0) + 1;
  }
  const COLORS = ['#6D28D9', '#7C3AED', '#8B5CF6', '#A78BFA', '#C4B5FD', '#DDD6FE'];
  return Object.entries(byCo)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6)
    .map(([country, users], i) => ({ country, users, fill: COLORS[i % COLORS.length] }));
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-40 text-gray-400 gap-2">
      <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center">
        <TrendingUp size={18} className="text-gray-300" />
      </div>
      <p className="text-xs font-medium">{label}</p>
    </div>
  );
}

// ─── Chart tooltip ─────────────────────────────────────────────────────────────

const CustomTooltip = ({ active, payload, label, formatter }: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
  formatter?: (v: number) => string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg px-4 py-3 text-sm">
      {label && <p className="font-bold text-gray-700 mb-1">{label}</p>}
      {payload.map((p) => (
        <p key={p.name} className="font-semibold" style={{ color: p.color }}>
          {p.name}: {formatter ? formatter(p.value) : p.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
};

// ─── KPI Card ──────────────────────────────────────────────────────────────────

function KPI({ label, value, sub, Icon, color, bg }: {
  label: string; value: string; sub?: string;
  Icon: ComponentType<{ size: number; className?: string }>;
  color: string; bg: string;
}) {
  return (
    <div className={`${bg} rounded-xl border border-gray-200 p-5`}>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-9 h-9 rounded-xl bg-white shadow-sm flex items-center justify-center flex-shrink-0">
          <Icon size={18} className={color} />
        </div>
        <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">{label}</p>
      </div>
      <p className={`text-3xl font-extrabold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export function AnalyticsPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [transactions, setTransactions] = useState<AdminTransaction[]>([]);
  const [tasks, setTasks] = useState<AdminTask[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [s, txs, ts, us] = await Promise.allSettled([
        adminApi.getStats(),
        adminApi.getTransactions(),
        adminApi.getTasks(),
        adminApi.getUsers(),
      ]);
      if (s.status === 'fulfilled') setStats(s.value);
      if (txs.status === 'fulfilled') setTransactions(txs.value);
      if (ts.status === 'fulfilled') setTasks(ts.value);
      if (us.status === 'fulfilled') setUsers(us.value);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const revenueData = useMemo(() => buildRevenueData(transactions), [transactions]);
  const userGrowthData = useMemo(() => buildUserGrowthData(users), [users]);
  const funnelData = useMemo(() => buildTaskFunnelData(tasks), [tasks]);
  const geoData = useMemo(() => buildGeoData(users), [users]);

  const totalRevenue = useMemo(() =>
    transactions.filter(t => t.status === 'completed').reduce((s, t) => s + Number(t.amount), 0),
    [transactions]
  );

  const completionRate = useMemo(() => {
    if (!tasks.length) return 0;
    return Math.round(tasks.filter(t => t.status === 'COMPLETED').length / tasks.length * 100);
  }, [tasks]);

  const formatXOF = (v: number) => v >= 1_000_000
    ? `${(v / 1_000_000).toFixed(1)}M XOF`
    : v >= 1_000 ? `${(v / 1_000).toFixed(0)}k XOF`
    : `${v} XOF`;

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-[#6D28D9]" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
          <p className="text-sm text-gray-600">Tableau de bord financier et opérationnel</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors">
          <RefreshCw size={15} />
          Actualiser
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI
          label="Revenu total"
          value={formatXOF(totalRevenue || (stats ? 0 : 0))}
          sub="Transactions complétées"
          Icon={DollarSign}
          color="text-green-700"
          bg="bg-green-50"
        />
        <KPI
          label="Utilisateurs"
          value={String(stats?.total_users ?? users.length)}
          sub={`${stats?.verified_users ?? users.filter(u => u.is_verified).length} vérifiés`}
          Icon={Users}
          color="text-blue-700"
          bg="bg-blue-50"
        />
        <KPI
          label="Tâches"
          value={String(stats?.total_tasks ?? tasks.length)}
          sub={`${stats?.completed_tasks ?? tasks.filter(t => t.status === 'COMPLETED').length} terminées`}
          Icon={Briefcase}
          color="text-purple-700"
          bg="bg-purple-50"
        />
        <KPI
          label="Taux complétion"
          value={`${completionRate}%`}
          sub="Tâches terminées / créées"
          Icon={TrendingUp}
          color="text-amber-700"
          bg="bg-amber-50"
        />
      </div>

      {/* Revenue + User growth */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue chart */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-bold text-gray-900">Revenu mensuel</h3>
              <p className="text-xs text-gray-400">6 derniers mois</p>
            </div>
            <DollarSign size={16} className="text-green-500" />
          </div>
          {revenueData.length === 0 ? (
            <EmptyChart label="Aucune transaction complétée pour l'instant" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={revenueData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6D28D9" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#6D28D9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} tickFormatter={(v) => v >= 1000 ? `${v / 1000}k` : String(v)} />
                <Tooltip content={<CustomTooltip formatter={formatXOF} />} />
                <Area type="monotone" dataKey="revenue" name="Revenu" stroke="#6D28D9" strokeWidth={2.5} fill="url(#revGrad)" dot={{ r: 4, fill: '#6D28D9', strokeWidth: 0 }} activeDot={{ r: 6 }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* User growth */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-bold text-gray-900">Croissance utilisateurs</h3>
              <p className="text-xs text-gray-400">Cumulatif sur 6 mois</p>
            </div>
            <Users size={16} className="text-blue-500" />
          </div>
          {userGrowthData.length === 0 ? (
            <EmptyChart label="Aucun utilisateur enregistré pour l'instant" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={userGrowthData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Line type="monotone" dataKey="clients" name="Clients" stroke="#3B82F6" strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="taskers" name="Taskers" stroke="#6D28D9" strokeWidth={2.5} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Task funnel + Geo distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Task funnel */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-bold text-gray-900">Entonnoir des tâches</h3>
              <p className="text-xs text-gray-400">Conversion de création à complétion</p>
            </div>
            <Briefcase size={16} className="text-purple-500" />
          </div>
          {tasks.length === 0 ? (
            <EmptyChart label="Aucune tâche créée pour l'instant" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={funnelData} layout="vertical" margin={{ top: 0, right: 20, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F3F4F6" />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis dataKey="label" type="category" tick={{ fontSize: 12, fill: '#6B7280', fontWeight: 600 }} axisLine={false} tickLine={false} width={72} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F5F3FF' }} />
                <Bar dataKey="value" name="Tâches" radius={[0, 8, 8, 0]}>
                  {funnelData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Geographic distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="text-sm font-bold text-gray-900">Distribution géographique</h3>
              <p className="text-xs text-gray-400">Utilisateurs par pays</p>
            </div>
          </div>
          {geoData.length === 0 ? (
            <EmptyChart label="Aucune donnée géographique disponible" />
          ) : (
            <div className="flex items-center gap-6">
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={geoData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} dataKey="users" paddingAngle={3}>
                    {geoData.map((entry, index) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => [`${v} utilisateurs`]} />
                </PieChart>
              </ResponsiveContainer>

              <div className="flex-1 space-y-2">
                {geoData.map((entry) => {
                  const total = geoData.reduce((s, e) => s + e.users, 0);
                  const pct = total ? Math.round(entry.users / total * 100) : 0;
                  return (
                    <div key={entry.country} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-sm flex-shrink-0" style={{ background: entry.fill }} />
                      <span className="text-xs font-bold text-gray-700 w-6">{entry.country}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                        <div className="h-1.5 rounded-full" style={{ width: `${pct}%`, background: entry.fill }} />
                      </div>
                      <span className="text-xs text-gray-400 w-8 text-right">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Transaction volume bar chart */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-sm font-bold text-gray-900">Volume de transactions</h3>
            <p className="text-xs text-gray-400">Nombre de transactions par mois</p>
          </div>
        </div>
        {revenueData.length === 0 ? (
          <EmptyChart label="Aucune donnée de volume disponible" />
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={revenueData} margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F3F4F6" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: '#F5F3FF' }} />
              <Bar dataKey="transactions" name="Transactions" fill="#6D28D9" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
