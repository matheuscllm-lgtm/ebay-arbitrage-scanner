# Public release checklist (manual, operator-only)

Goal: make this repo **public** so GitHub Actions is free, while reducing
**casual discovery**. This is *not* real security — anyone with the link (or
using GitHub code search) can read everything. For truly private results, run
scans locally.

Do these on github.com **after** this PR is merged. Nothing here flips the repo
public automatically — every step is a manual choice.

## 0. Delete stale remote branches

After merging this PR, delete the work branch:

```bash
git push origin --delete chore/prepare-public-release
```

There are **no other remote branches** to delete (only `main` and this PR
branch exist on the remote).

## 1. Neutralize repo metadata (Settings → General)

- [ ] **Rename** the repository to something generic (the current name is a
      giveaway). Suggestion: `price-compare-tool` or similar.
- [ ] Clear the **Description**.
- [ ] Clear all **Topics / tags**.

## 2. Disable public interaction surfaces (Settings)

- [ ] **Issues**: off (Settings → General → Features).
- [ ] **Wiki**: off.
- [ ] **Discussions**: off.
- [ ] **Projects**: off.
- [ ] **Pages**: set Source to **None** (Settings → Pages).

## 3. Flip to public

- [ ] Settings → General → Danger Zone → **Change visibility → Public**.
- [ ] Confirm the prompt.

## 4. Validate free Actions

- [ ] Open the **Actions** tab → run the `tests` workflow (push or
      `workflow_dispatch`) → confirm it is **green** and billed as free
      (public repos get unlimited standard runners).

## Residual risk (read once)

- A public repo means any future Actions **logs and artifacts are
  world-downloadable** by anyone who finds the repo. Keep scan output local;
  don't push result files or run result-producing jobs in public CI.
- Code filenames, imports and the marketplace category id remain findable via
  **GitHub code search**. The README scrub is cosmetic only.
- `CLAUDE.md` stays keyword-heavy (it's the operational guide). Trim or untrack
  it too if you want the repo fully neutral.
- The real target list (`watchlist.yaml`) and the method doc (`METODO.md`) are
  now git-ignored and stay local — they are not in the published repo.
