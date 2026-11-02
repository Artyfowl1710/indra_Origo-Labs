# Create and push the private GitHub repository

The GitHub integration available to this assistant can list and write files to an **existing** repository, but does not expose a create-repository action. Therefore no new GitHub repository has been created from this session. Use the following one-time process to create the private repo under your account and push this prepared source tree.

## Recommended name

`indra-origo` (private). If that name already exists, use `indra-origo-workstation`.

## 1. Create the private repository

1. Sign into GitHub as `Artyfowl1710`.
2. Open https://github.com/new
3. Repository name: `indra-origo`.
4. Select **Private**.
5. Do not initialize with a README, `.gitignore`, or license—the source tree already has a README and ignore rules.
6. Create the repository. Copy its HTTPS clone URL.

## 2. Extract and push (PowerShell)

Extract the release ZIP, then open PowerShell in the extracted `indra_origo_v1_7_2` folder. Before the first commit, inspect the source and confirm there are no personal files or secrets.

```powershell
git init
git branch -M main
git add .
git status --short
# Stop here if .env, data/, logs/, .venv/, tokens, databases or private files appear.
git diff --cached --stat
git diff --cached
# Authenticate with Git Credential Manager or GitHub CLI before pushing.
git remote add origin https://github.com/Artyfowl1710/indra-origo.git
git commit -m "Initial private release: Indra Origo v1.7.2"
git push -u origin main
```

If you use GitHub CLI, authenticate first with `gh auth login`. You may create the private repository with `gh repo create Artyfowl1710/indra-origo --private --source . --remote origin --push`, but only do so from the reviewed project root and after confirming `gh auth status` identifies the correct account.

## 3. Verify privacy and content

- Confirm repository Settings → General says **Private**.
- Confirm only intended collaborators are present.
- Confirm `.env`, `data/`, `workspace/`, logs, `.venv/`, signing keys, APKs and credentials are not tracked.
- Run a secret scanner on the repository and rotate any accidentally committed secret immediately.
- Review GitHub Actions permissions and avoid workflows with write permissions unless required.
- Enable two-factor authentication and review connected OAuth apps/tokens.

## 4. Future updates

```powershell
git status --short
git add <specific-reviewed-paths>
git diff --cached
git commit -m "Describe the change"
git push
```

Do not `git add -f` ignored local state. Never store an APK signing keystore or production token in Git; use a dedicated secret manager for release workflows.
