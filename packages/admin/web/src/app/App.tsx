import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { LoginPage } from "../features/auth/LoginPage";
import { SESSION_EXPIRED, useSessionStore } from "../features/auth/sessionStore";
import { probeMode, fetchResources } from "../features/resources/api";
import { AppShell } from "../features/shell/AppShell";
import { applyTheme, useShellStore } from "../shared/stores/shell";
import { ErrorBoundary } from "../shared/ui/ErrorBoundary";

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5_000 },
  },
});

function Boot() {
  const hydrate = useSessionStore((s) => s.hydrate);
  const authorization = useSessionStore((s) => s.authorization);
  const logout = useSessionStore((s) => s.logout);
  const {
    demoForced,
    setDemoMode,
    setApiVersion,
    setBranding,
    themePref,
    reducedTransparency,
    density,
    toast,
    toasts,
    dismissToast,
    setRoute,
  } = useShellStore();
  const [ready, setReady] = useState(false);
  const [demo, setDemo] = useState(false);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [bootKey, setBootKey] = useState(0);

  useEffect(() => {
    hydrate();
    applyTheme(themePref, reducedTransparency, density);
  }, [hydrate, themePref, reducedTransparency, density]);

  useEffect(() => {
    const onExpired = () => {
      // logout already done in emitSessionExpired (once); clear caches + toast once
      qc.clear();
      toast("Session expired — sign in again", "error");
      setRoute({ page: "overview" });
    };
    window.addEventListener(SESSION_EXPIRED, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED, onExpired);
  }, [toast, setRoute]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setReady(false);
      const result = await probeMode(demoForced);
      if (cancelled) return;
      setDemo(result.demo);
      setDemoMode(result.demo);
      setApiVersion(result.meta.version);
      if (result.meta.branding) setBranding(result.meta.branding);
      setNeedsAuth(!result.demo);
      if (result.demo && !demoForced) {
        toast("API offline — using interactive demo data");
      }
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoForced, bootKey]);

  const canLoadResources = ready && (demo || Boolean(authorization));
  const showLogin = ready && !demo && needsAuth && !authorization;

  const resourcesQ = useQuery({
    queryKey: ["resources", demo, Boolean(authorization)],
    queryFn: () => fetchResources(demo),
    enabled: canLoadResources,
  });

  if (!ready) {
    return (
      <div className="login-page">
        <div className="muted">Loading…</div>
      </div>
    );
  }

  if (showLogin) {
    return (
      <>
        <LoginPage />
        <div className="toast-stack">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`toast${t.kind === "error" ? " error" : ""}`}
              onClick={() => dismissToast(t.id)}
            >
              {t.message}
            </div>
          ))}
        </div>
      </>
    );
  }

  if (canLoadResources && resourcesQ.isLoading) {
    return (
      <div className="login-page">
        <div className="muted">Loading AdminBoard…</div>
      </div>
    );
  }

  if (resourcesQ.isError) {
    return (
      <div className="login-page">
        <div className="alert error">
          {(resourcesQ.error as Error).message}
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              logout();
              setBootKey((k) => k + 1);
            }}
          >
            Back to sign in
          </button>
          <button type="button" className="btn btn-sm" onClick={() => resourcesQ.refetch()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary onReset={() => setBootKey((k) => k + 1)}>
      <AppShell resources={resourcesQ.data ?? []} demo={demo} />
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Boot />
    </QueryClientProvider>
  );
}
