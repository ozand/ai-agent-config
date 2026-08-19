import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

/** Compact large-context sessions after they cross the 272K operating ceiling. */
const COMPACT_THRESHOLD_TOKENS = 272_000;
const EPHEMERAL_SESSION_KEY = "ephemeral";

export default function registerAutoCompact272k(pi: ExtensionAPI): void {
  const pendingSessions = new Set<string>();

  const sessionKey = (ctx: ExtensionContext): string =>
    ctx.sessionManager.getSessionId() || EPHEMERAL_SESSION_KEY;

  pi.on("session_shutdown", (_event, ctx) => {
    pendingSessions.delete(sessionKey(ctx));
  });

  pi.on("turn_end", (_event, ctx) => {
    const model = ctx.model;
    if (!model || model.contextWindow <= COMPACT_THRESHOLD_TOKENS) {
      return;
    }

    const usage = ctx.getContextUsage();
    const key = sessionKey(ctx);
    if (
      !usage ||
      usage.tokens <= COMPACT_THRESHOLD_TOKENS ||
      pendingSessions.has(key)
    ) {
      return;
    }

    pendingSessions.add(key);
    if (ctx.hasUI) {
      ctx.ui.notify(
        `Context exceeded 272K on ${model.id}; starting compaction`,
        "info",
      );
    }

    ctx.compact({
      customInstructions:
        "Preserve the active goal, constraints, decisions, changed files, validation evidence, failures, and exact next steps.",
      onComplete: () => pendingSessions.delete(key),
      onError: (error) => {
        pendingSessions.delete(key);
        if (ctx.hasUI) {
          ctx.ui.notify(`272K auto-compaction failed: ${error.message}`, "error");
        }
      },
    });
  });
}
