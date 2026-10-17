import type { BbPluginApi } from "@get-bb/plugin-sdk";
import { registerLauncher } from "./src/launcher-server.js";
import { REASONING_LEVELS, reasoningLabel, reasoningDescription } from "./src/reasoning.js";

// `experimental_picker` is an optional hint for BB builds that can relabel the
// model picker and require a project before listing agents. Published BB reads
// only `models.scope` and `models.fallback` and ignores it, showing its default
// picker; `model/list` then scopes agents by the workspace path.
const agentCatalog = { scope: "workspace" as const, fallback: [], experimental_picker: { label: "Agents", selectPlaceholder: "Select an agent", projectRequiredMessage: "Select a Gas City project (city or rig) to see its agents.", searchPlaceholder: "Search agents", requiresProject: true } };

export default function plugin(bb: BbPluginApi) {
  registerLauncher(bb);
  bb.providers.register({
    id: "gas-city", displayName: "Gas City", icon: "Building2",
    strings: {
      signInHint: "Run gc bb install and gc bb connect on the selected BB host.",
      expiredHint: "Run gc bb status on the selected BB host.",
      installUrl: "https://github.com/gastownhall/gascity-packs/tree/main/bb",
    },
    maintenance: { health: true, usage: false, installation: false },
    capabilities: {
      permissionModes: ["full"], reasoningLevels: REASONING_LEVELS, fork: "none",
      supportsNativeUserQuestion: true, supportsManualCompaction: false,
      supportsThreadArchive: false, supportsThreadRename: false, supportsServiceTier: false,
    },
    reasoningLevels: REASONING_LEVELS.map(id => ({ id, label: reasoningLabel(id), description: reasoningDescription(id) })),
    composerActions: [], models: agentCatalog,
    env: { passthrough: ["GC_BB_CONFIG", "GC_BB_AUTH_TOKEN", "XDG_CONFIG_HOME", "XDG_STATE_HOME"] },
    deriveProviderOptions(context) {
      return { projectId: context.projectId, bbThreadId: context.threadId };
    },
  });
}
