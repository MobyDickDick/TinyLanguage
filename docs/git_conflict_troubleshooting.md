# Git conflict troubleshooting (VS Code)

When VS Code shows a status bar message like `TinyLanguage#103 has conflicts`, it means the branch or pull request you opened cannot be merged cleanly with the target branch (usually `main`). VS Code surfaces this via its GitHub Pull Request or built-in source control integration.

## Why it happens

- The target branch advanced after your branch was created (new commits on `main`).
- Both branches edited the same files or nearby lines, so Git cannot auto-merge.

## How to resolve

1. **Update your branch with the latest target branch**
   - In VS Code: open the Source Control view, click `...` → **Pull** (or **Pull from...** to ensure `origin/main`).
   - CLI equivalent: `git fetch origin` then `git rebase origin/main` (or `git merge origin/main`).
2. **Resolve conflicts**
   - VS Code will mark conflicted files and offer **Accept Current/Incoming/Both/Compare Changes** actions. Edit until files no longer contain conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
3. **Commit the resolutions**
   - Stage and commit the resolved files (`git add ...`, `git commit`).
4. **Push the updated branch**
   - `git push` (or `git push --force-with-lease` if you rebased).

Once the branch rebases or merges cleanly onto the target branch, the "has conflicts" badge disappears and the pull request can be merged.
