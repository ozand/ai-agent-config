# Sharing Pi prompts safely

## What this repository includes

`clients/pi/prompts/` contains reviewed, generic prompt templates that are suitable for reuse across projects. Pi loads direct Markdown children of its user or project prompt directory as slash commands; the command name comes from the template filename. For example, `git-sync-status.md` is available as `/git-sync-status` when installed in the prompt directory.

These files are copied from local personal prompts only after review and sanitization. Local prompts are not imported wholesale.

## Shareable Pi resources

Based on the official Pi documentation:

- **Prompt templates** are Markdown prompts with optional frontmatter and argument substitutions. They are the lightest-weight shareable unit when no executable behavior is needed. See [Prompt Templates](https://pi.dev/docs/latest/prompt-templates).
- **Skills** are suitable for reusable specialized instructions and supporting files. A portable skill is a directory containing `SKILL.md`; include only reviewed, necessary support files and explain dependencies. See [Skills](https://pi.dev/docs/latest/skills).
- **Extensions** can add executable commands, tools, and behavior. Share them only when code, dependencies, compatibility, and security implications are reviewed; they are not just prompt text. See [Extensions](https://pi.dev/docs/latest/extensions).
- **Non-secret settings examples** may be shared as templates when they are client-independent and do not expose host-specific paths, private preferences, or runtime state. Project trust and configuration precedence must be documented. See [Settings](https://pi.dev/docs/latest/settings).
- **Package manifests** may be useful for distributing groups of prompts, skills, and extensions, but create a dependency and release surface; add them only when a package is an intentional product. See [Pi Packages](https://pi.dev/docs/latest/packages).

The slash-command menu is session-dependent: built-ins and commands contributed by loaded resources can differ. Use the running Pi `/` menu as the runtime discovery check; the static documentation describes built-ins and extension points, not the exact contents of a particular user's session.

## Keep local or private

Do not copy personal prompt files to this repository without review. Keep out:

- credentials, tokens, cookies, OAuth/account state, or secret-file contents;
- personal or customer information and private task transcripts;
- machine-specific paths, usernames, hostnames, internal service names, or private repository locations;
- session, trust, cache, or other generated runtime state;
- instructions that disclose private organizational procedures or assume private agents/tools without documenting a safe, public alternative.

Local prompt configuration under `%USERPROFILE%\.pi\agent\prompts` is ignored by the repository. Only explicitly reviewed files under `clients/pi/prompts/` are candidates for sharing.

## Review checklist before adding a prompt

1. Confirm its goal and audience are broadly reusable.
2. Remove machine-specific details, secrets, personal data, and unrelated session context.
3. Replace assumptions about private agents, tools, repositories, or credentials with explicit prerequisites or generic alternatives.
4. Verify its frontmatter and argument substitutions against the official prompt-template documentation.
5. Check that the prompt does not direct unsafe or irreversible actions without an approval gate.
6. Add it under `clients/pi/prompts/`, link it from the Pi README, and review the staged diff by allowlist.
7. After installation, run `/reload` and verify the command appears in Pi's `/` menu. A file existing in the repository alone does not prove runtime discovery.
