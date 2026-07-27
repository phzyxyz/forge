/**
 * Platform-coupled env helpers — keep Forge env aligned with AdminBoard host.
 */
import type { Environment, EnvVariable } from "./types";
import { normalizeEnvVariable } from "./types";

export const PLATFORM_ENV_ID = "env_local";

/** Built-in platform variables for the active AdminBoard mount. */
export function platformVariables(baseUrl: string, username?: string | null): EnvVariable[] {
  const vars: EnvVariable[] = [
    {
      key: "baseUrl",
      value: baseUrl,
      enabled: true,
      secret: false,
      source: "platform",
      locked: true,
      editable: false,
      description: "This AdminBoard server origin (platform)",
    },
  ];
  if (username) {
    vars.push({
      key: "sessionUser",
      value: username,
      enabled: true,
      secret: false,
      source: "platform",
      locked: true,
      editable: false,
      description: "Signed-in AdminBoard user (platform)",
    });
  }
  return vars;
}

export function userSecretStubs(): EnvVariable[] {
  return [
    {
      key: "token",
      value: "",
      enabled: true,
      secret: true,
      source: "user",
      locked: false,
      editable: true,
      description: "Bearer token for {{token}}",
    },
    {
      key: "apiKey",
      value: "",
      enabled: true,
      secret: true,
      source: "user",
      locked: false,
      editable: true,
      description: "API key for {{apiKey}}",
    },
  ];
}

/** Merge platform baseUrl (and optional session) into an environment without wiping user vars. */
export function syncPlatformIntoEnv(
  env: Environment,
  opts: { baseUrl: string; username?: string | null; forceBaseUrl?: boolean },
): Environment {
  const platform = platformVariables(opts.baseUrl, opts.username);
  const byKey = new Map(env.variables.map((v) => [v.key, normalizeEnvVariable(v)]));

  for (const p of platform) {
    const existing = byKey.get(p.key);
    if (!existing) {
      byKey.set(p.key, p);
      continue;
    }
    // Platform keys: refresh value from host when not user-editable
    if (!isEditableValue(existing) || opts.forceBaseUrl) {
      byKey.set(p.key, {
        ...existing,
        ...p,
        // keep enabled if user toggled? platform always enabled
        enabled: true,
        value: p.value,
      });
    } else {
      byKey.set(p.key, {
        ...existing,
        source: "platform",
        locked: true,
        description: existing.description || p.description,
      });
    }
  }

  // Ensure secret stubs exist for user
  for (const stub of userSecretStubs()) {
    if (!byKey.has(stub.key)) byKey.set(stub.key, stub);
  }

  // Platform vars first, then user
  const ordered: EnvVariable[] = [];
  for (const p of platform) {
    const v = byKey.get(p.key);
    if (v) {
      ordered.push(v);
      byKey.delete(p.key);
    }
  }
  for (const v of byKey.values()) ordered.push(normalizeEnvVariable(v));

  return { ...env, variables: ordered };
}

function isEditableValue(v: EnvVariable): boolean {
  return normalizeEnvVariable(v).editable !== false;
}

export function normalizeEnvironment(env: Environment): Environment {
  return {
    ...env,
    variables: env.variables.map(normalizeEnvVariable),
  };
}
