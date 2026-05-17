# Deploy pipeline

## TL;DR

| Command | Does what |
|---|---|
| `packaging\deploy.bat` | Site-only change → live in ~20s |
| `packaging\release.bat 0.1.1` | New version: build .exe → installer → GitHub Release → redeploy site |

Both use the CLIs already authed on this machine (`gh`, `vercel`).

---

## Where things live

| Thing | Where |
|---|---|
| Code repo | https://github.com/vladleonte27/veet (public) |
| Installer downloads | GitHub Releases (`releases/latest/download/Veet-Setup.exe`) |
| Site hosting | Vercel project `veet` (Owner: `vladleonte27`) |
| Vercel preview URL | https://veet-iota.vercel.app |
| Production domain | https://veet.space *(pending DNS — see below)* |

The "Install for Windows" buttons on the site point to:
`https://github.com/vladleonte27/veet/releases/latest/download/Veet-Setup.exe`

That URL always serves the **latest** release, so you never have to touch the
site after cutting a new version — just `release.bat <version>`.

---

## One-time DNS setup (you, in Namecheap)

Vercel wants you to point `veet.space` at it. **Easiest path** — change
the nameservers, Vercel manages DNS for you.

1. Log in to **Namecheap**.
2. **Domain List** → **Manage** next to `veet.space`.
3. On the **Domain** tab, find **NAMESERVERS** section.
4. Change "Namecheap BasicDNS" → **Custom DNS**.
5. Enter:
   - `ns1.vercel-dns.com`
   - `ns2.vercel-dns.com`
6. Save (green checkmark).

Propagation: 5 min – 30 min typically (up to 24h in worst case). Once DNS
resolves, Vercel auto-issues the SSL cert and `https://veet.space` goes live.

To check: in a new terminal,
`Resolve-DnsName veet.space -Type NS` — should return the Vercel nameservers.

Once green, re-run from `website/`:
`vercel alias set veet-iota.vercel.app veet.space`

---

## Ongoing workflow

### Edit copy / styling
1. Tweak `website/index.html`.
2. Run `packaging\deploy.bat`.
3. Live in ~20 seconds.

### Ship a new app version
1. Bump the version mentally (e.g., 0.1.0 → 0.1.1).
2. Run `packaging\release.bat 0.1.1`.
3. Script bumps `installer.iss`, builds `Veet.exe`, compiles installer,
   uploads `Veet-Setup.exe` to GitHub Releases as `v0.1.1`, redeploys site.
4. Every user who clicks "Install for Windows" now gets the new build.

### Force a re-deploy without changes
`packaging\deploy.bat` works even without edits.

---

## Files in this layout

```
.
├── veet.py                 # Windows app (Python)
├── veet.spec               # PyInstaller spec
├── packaging/
│   ├── build.bat           # build .exe (cpu|gpu)
│   ├── installer.iss       # Inno Setup script
│   ├── gen_icons.py        # regenerate brand icons from veet-logo.jpg
│   ├── release.bat         # ← full release pipeline
│   └── deploy.bat          # ← site-only deploy
├── website/
│   ├── index.html
│   ├── vercel.json
│   └── assets/             # icon.png, icon-mark.png
├── assets/
│   ├── Inter.ttf
│   ├── chime-start.wav
│   ├── chime-stop.wav
│   ├── icon.png            # used on site (with cyan glow)
│   ├── icon-mark.png       # transparent (tray icon, etc.)
│   └── icon.ico            # multi-res Windows icon
├── DEPLOY.md               # this file
├── BRAND.md                # design tokens
└── README.md               # placeholder
```
