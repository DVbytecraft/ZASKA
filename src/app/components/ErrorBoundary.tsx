import { Component, type ReactNode } from "react";

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("Unhandled UI error", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="size-full flex items-center justify-center p-6 bg-white">
          <div className="text-center">
            <h2 className="text-xl font-bold text-gray-900 mb-2">Une erreur est survenue</h2>
            <p className="text-sm text-gray-600 mb-4">Rechargez la page pour continuer.</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-[#6D28D9] text-white"
            >
              Recharger
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
