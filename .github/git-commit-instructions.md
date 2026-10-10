# Git Commit Message Guidelines

## General Rules

* **Always use the Conventional Commits format**
  `<type>(<optional scope>): <short imperative summary>`
* Use the **imperative mood** (e.g., add, fix, remove; not added or fixes).
* Keep the summary **concise and specific** (≤ 72 characters).
* Use **lowercase** for the type and summary.
* Do **not** end the summary with a period.
* If multiple changes exist, choose the **most impactful** type.
* Avoid bundling unrelated changes in a single commit.

---

## Allowed Commit Types

| Type       | When to Use                                         |
| ---------- | --------------------------------------------------- |
| `feat`     | Add or change user-facing functionality             |
| `fix`      | Fix a bug or incorrect behavior                     |
| `refactor` | Change internal structure without changing behavior |
| `test`     | Add or update tests                                 |
| `docs`     | Update documentation or comments                    |
| `style`    | Formatting-only changes (no logic impact)           |
| `chore`    | Maintenance, tooling, or non-runtime changes        |
| `ci`       | CI/CD configuration or pipeline changes             |

---

## Commit Message Examples

### Feature

* `feat: add offline cache support`

### Bug Fix

* `fix: prevent crash when token is null`

### Refactor

* `refactor: extract network retry logic`

### Updating Markdown

* `docs: update README with new setup instructions`

### Updating Code Comments

* `docs: clarify parameter usage in DataStore class`

### Updating Github Workflows

* `ci: add workflow for automated release on tag`

---

## Dependency Changes

Use the `deps` scope under `chore`.

* **Update a dependency**
  `chore(deps): update kotlinx-coroutines to 1.8.1`

* **Add a dependency**
  `chore(deps): add okhttp 4.12.0`

* **Remove a dependency**
  `chore(deps): remove legacy-support library`

---

## Documentation Changes

For README updates, comments, or guides:

* `docs: clarify setup steps for local development`

---

## Test Changes

For adding or modifying tests only:

* `test: add unit tests for auth refresh logic`

---

## Breaking Changes

If a change breaks compatibility, add `!` after the type and describe the impact in the commit body:

* `feat!: remove deprecated auth endpoint`

---

## Notes

* Use scopes (e.g., `feat(api):`, `fix(ui):`) when they improve clarity (optional).
* Follow Semantic Versioning when applicable.
* Keep commit history clean, readable, and intentional.
