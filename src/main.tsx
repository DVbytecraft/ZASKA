import { createRoot } from "react-dom/client";
import App from "./app/App.tsx";
import "./styles/index.css";
import "./i18n";

// Register service worker for PWA installability + offline support
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // SW registration failed silently — app still works online
    });
  });
}

createRoot(document.getElementById("root")!).render(<App />);
