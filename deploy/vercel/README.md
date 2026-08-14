# Moved

The Vercel landing now lives at the **repository root** (`app/`, `package.json`).

If Production shows `NOT_FOUND` / 404:

1. Vercel → Project → **Settings → General → Root Directory**
2. Clear `deploy/vercel` — leave it **empty**
3. Save
4. Deployments → latest `master` → **Promote to Production**
   (do not use Redeploy → Production in the modal)

Preview can keep working; Production needs a real Production deploy of root Next.js.
