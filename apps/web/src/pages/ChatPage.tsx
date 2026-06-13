import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, getWsBaseUrl, type ChatMessage } from "../api";

type ChatEvent = ChatMessage | { message: string; senderId?: string };

export function ChatPage() {
  const { taskId = "" } = useParams();
  const [messages, setMessages] = useState<ChatEvent[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    (async () => {
      const res = await api.listChat(taskId);
      if (res.success) setMessages(res.data ?? []);
    })();
  }, [taskId]);

  useEffect(() => {
    if (!taskId) return;
    let cancelled = false;
    const base = getWsBaseUrl();

    (async () => {
      const tr = await api.issueWsTicket();
      if (cancelled) return;
      if (!tr.success || !tr.data?.ticket) {
        setError(tr.error ?? "Impossible d'émettre un ticket WebSocket");
        return;
      }
      const ws = new WebSocket(`${base}/ws/tasks/${taskId}`);
      wsRef.current = ws;
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "auth", ticket: tr.data.ticket }));
      };
      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          setMessages((prev) => [...prev, parsed]);
        } catch {
          setMessages((prev) => [...prev, { message: event.data }]);
        }
      };
      ws.onerror = () => setError("WebSocket error");
    })();

    return () => {
      cancelled = true;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [taskId]);

  return (
    <div className="space-y-3">
      <h2 className="text-xl font-semibold">Chat</h2>
      {error ? <p className="text-red-600">{error}</p> : null}
      <div className="border rounded p-3 h-80 overflow-auto bg-white space-y-2">
        {messages.map((m, idx) => (
          <p key={idx} className="text-sm">
            <span className="font-semibold">{m.senderId ?? "system"}:</span> {m.message}
          </p>
        ))}
      </div>
      <div className="flex gap-2">
        <input className="flex-1 border rounded p-2" value={input} onChange={(e) => setInput(e.target.value)} />
        <button
          className="bg-black text-white rounded px-3"
          onClick={async () => {
            if (!input.trim()) return;
            const text = input;
            setInput("");
            await api.sendChat(taskId, text);
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
