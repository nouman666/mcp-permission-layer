# Publish this artifact to GitHub (2 minutes)

Local folder is ready:

`C:\Users\as\Desktop\bodmas\mcp-permission-layer`

## Option A — GitHub website (easiest)

1. Open https://github.com/new
2. Repository name: **`mcp-permission-layer`**
3. Visibility: **Public**
4. Do **not** add README / license (already included)
5. Click **Create repository**
6. In PowerShell:

```powershell
cd C:\Users\as\Desktop\bodmas\mcp-permission-layer
gh auth login
# follow browser login, then:
gh repo create mcp-permission-layer --public --source=. --remote=origin --push
```

If `gh repo create` fails because the empty repo already exists on the website:

```powershell
cd C:\Users\as\Desktop\bodmas\mcp-permission-layer
git remote add origin https://github.com/YOUR_USERNAME/mcp-permission-layer.git
git push -u origin main
```

7. Copy the final URL, e.g. `https://github.com/YOUR_USERNAME/mcp-permission-layer`
8. Tell me the URL — I will put it into the paper Data Availability Statement.

## Option B — only CLI

```powershell
cd C:\Users\as\Desktop\bodmas\mcp-permission-layer
gh auth login
gh repo create mcp-permission-layer --public --source=. --remote=origin --push
```
