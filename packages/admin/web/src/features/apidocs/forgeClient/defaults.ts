import {
  FORGE_CLIENT_FORMAT,
  FORGE_CLIENT_VERSION,
  type ClientSettings,
  type Environment,
  type ForgeClientDocument,
} from "./types";
import { PLATFORM_ENV_ID, platformVariables, userSecretStubs } from "./envPlatform";

export function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`;
}

export function defaultSettings(): ClientSettings {
  return {
    hideAdminApis: true,
    adminPathPrefixes: ["/admin"],
    docsPathPrefixes: ["/docs", "/redoc", "/openapi.json"],
    historyLimit: 40,
    timeoutMs: 30_000,
  };
}

export function defaultEnvironments(baseUrl?: string): Environment[] {
  const origin =
    baseUrl ||
    (typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8000");
  return [
    {
      id: PLATFORM_ENV_ID,
      name: "This server",
      variables: [...platformVariables(origin), ...userSecretStubs()],
    },
    {
      id: "env_custom",
      name: "Custom base",
      variables: [
        {
          key: "baseUrl",
          value: origin,
          enabled: true,
          secret: false,
          source: "user",
          locked: true, // key stays baseUrl
          editable: true, // value free to change
          description: "Override origin for another host (CORS required)",
        },
        ...userSecretStubs(),
      ],
    },
  ];
}

export function emptyDocument(mode: "sandbox" | "workspace" = "sandbox"): ForgeClientDocument {
  const envs = defaultEnvironments();
  return {
    format: FORGE_CLIENT_FORMAT,
    version: FORGE_CLIENT_VERSION,
    mode,
    activeEnvironmentId: envs[0]!.id,
    settings: defaultSettings(),
    environments: envs,
    collections: [],
    history: [],
    savedResponses: [],
  };
}

export function isForgeClientDocument(v: unknown): v is ForgeClientDocument {
  if (!v || typeof v !== "object") return false;
  const d = v as Partial<ForgeClientDocument>;
  return (
    d.format === FORGE_CLIENT_FORMAT &&
    d.version === FORGE_CLIENT_VERSION &&
    Array.isArray(d.environments) &&
    Array.isArray(d.collections)
  );
}
