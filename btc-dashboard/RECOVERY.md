# Repository History Rewritten — Recovery Instructions

We rewrote the repository history to remove runtime artifacts (`btc-dashboard/logs` and `btc-dashboard/app/__pycache__`). A mirror backup was created at `../Nodecontrol-mirror.git`.

If you have a local clone of this repository, please follow one of these options.

Recommended (clean, safe):

1. Re-clone the repository:

```bash
git clone https://github.com/Alarique-Zayin/Nodecontrol.git
```

Alternative (if you cannot re-clone):

1. Ensure any local work is saved (create patches or branch backups).
2. Reset your local branches to match remote (this will discard local commits that are not pushed):

```bash
git fetch origin
git checkout main
git reset --hard origin/main
git clean -fdx
```

Notes:
- The rewritten history was force-pushed to `origin`. Collaborators must re-clone or reset any local copies to avoid conflicts.
- A backup mirror was created at `../Nodecontrol-mirror.git` on the machine that performed the rewrite.
- If you need assistance restoring branches or patches, contact the repo owner.
