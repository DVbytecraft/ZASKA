import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type NotificationItem } from "../api";

function formatNotificationDate(value: string) {
  return new Date(value).toLocaleString("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function notificationTone(type: string) {
  switch (type) {
    case "success":
      return "border-green-200 bg-green-50";
    case "warning":
      return "border-amber-200 bg-amber-50";
    case "error":
      return "border-red-200 bg-red-50";
    default:
      return "border-gray-200 bg-white";
  }
}

export function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [markingAll, setMarkingAll] = useState(false);

  const unreadCount = useMemo(
    () => notifications.filter((item) => !item.read).length,
    [notifications],
  );

  async function loadNotifications() {
    setLoading(true);
    const res = await api.getNotifications();
    if (res.success) {
      setNotifications(res.data);
    }
    setLoading(false);
  }

  useEffect(() => {
    void loadNotifications();
  }, []);

  async function handleMarkRead(notificationId: string) {
    const res = await api.markNotificationRead(notificationId);
    if (!res.success) return;
    setNotifications((current) =>
      current.map((item) =>
        item.id === notificationId ? { ...item, read: true } : item,
      ),
    );
  }

  async function handleMarkAllRead() {
    setMarkingAll(true);
    const res = await api.markAllNotificationsRead();
    if (res.success) {
      setNotifications((current) =>
        current.map((item) => ({ ...item, read: true })),
      );
    }
    setMarkingAll(false);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Notifications</h2>
          <p className="text-sm text-gray-500">
            Suivi des alertes compte, KYC, messages et activite.
          </p>
        </div>
        <button
          className="rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50"
          disabled={unreadCount === 0 || markingAll}
          onClick={() => void handleMarkAllRead()}
        >
          {markingAll ? "Mise a jour..." : "Tout marquer comme lu"}
        </button>
      </div>

      {loading ? (
        <div className="rounded-xl border bg-white p-6 text-sm text-gray-400">
          Chargement des notifications...
        </div>
      ) : notifications.length === 0 ? (
        <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
          Aucune notification pour le moment.
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((item) => (
            <div
              key={item.id}
              className={`rounded-xl border p-4 shadow-sm transition ${notificationTone(item.type)} ${
                item.read ? "opacity-80" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900">{item.title}</h3>
                    {!item.read && (
                      <span className="rounded-full bg-black px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                        Nouveau
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700">{item.body}</p>
                  <p className="text-xs text-gray-500">
                    {formatNotificationDate(item.created_at)}
                  </p>
                </div>
                {!item.read && (
                  <button
                    className="rounded-lg border px-3 py-1.5 text-xs font-medium"
                    onClick={() => void handleMarkRead(item.id)}
                  >
                    Marquer lu
                  </button>
                )}
              </div>
              {item.task_id && (
                <div className="mt-3">
                  <Link
                    className="text-sm font-medium text-black underline underline-offset-2"
                    to={`/tasks/${item.task_id}`}
                  >
                    Ouvrir la tache
                  </Link>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
