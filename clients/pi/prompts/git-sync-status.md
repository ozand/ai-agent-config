---
description: Fetch remote changes and report Git synchronization status
argument-hint: "[remote]"
---
Fetch remote updates and report the synchronization status of the current Git repository against `${1:-origin}`.

Actions:
1. Confirm that the current directory is inside a Git repository. If not, report that and stop.
2. Determine the current branch, its upstream, and the selected remote. Do not modify working files, history, or branches.
3. Run a safe `git fetch --prune` for the selected remote. If fetch fails, briefly report why and continue using available local data, clearly marking it as potentially stale.
4. Separately identify:
   - uncommitted local changes: staged, unstaged, and untracked;
   - local commits not yet pushed to the upstream branch;
   - remote commits pending locally and available to pull;
   - branch divergence or a missing upstream, when applicable.
5. Do not commit, pull, push, merge, or rebase.
6. Do not expose secrets from file contents or credential-bearing remote URLs.

Output a concise report:
- **Repository / branch / upstream**
- **Fetch** — success or error
- **Uncommitted local changes**
- **Unpushed commits**
- **Pending remote updates**
- **Summary** — `in sync`, `push needed`, `pull needed`, `branches diverged`, or `no upstream`

Explicitly write "None" for every empty category.
