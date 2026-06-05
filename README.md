# Healthsites Campaign Site 2026

[MIT License](LICENSE) © 2026 healthsites.io

The Healthsites.io 2026 campaign site. Built with [Pelican](https://getpelican.com)
(a Python static-site generator) with multilingual support (EN / FR / PT / AR) via
`i18n_subsites`. The published HTML is served from **https://campaigns.healthsites.io**
through GitHub Pages.

## Requirements

- Python 3.12+
- The packages in `requirements.txt` (`pelican`, `markdown`, `pelican-i18n-subsites`)

## Local development

```bash
# Clone
git clone git@github.com:healthsites/campaign-site-2026.git
cd campaign-site-2026

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Build and serve with live reload at http://localhost:8000
make serve
```

Other Make targets:

| Command        | What it does                                        |
| -------------- | --------------------------------------------------- |
| `make build`   | Build the site (development settings) into `output/`|
| `make serve`   | Build, then serve locally with autoreload           |
| `make publish` | Build with production settings (`publishconf.py`)   |
| `make clean`   | Remove the `output/` directory                       |

## How it's structured

```text
content/            # Markdown source — pages, campaigns, translations
  campaigns/        #   per-country campaign pages (+ -fr/-pt/-ar variants)
  about*.md         #   about pages
  index*.md         #   homepage copy per language
theme/
  templates/        # Jinja2 templates (base, index, country, region, …)
  static/
    css/vanilla.css # All styles
    js/             # Small vanilla JS (typing effect, nav)
    images/         # Site imagery
pelicanconf.py      # Base build config (dev)
publishconf.py      # Production overrides (custom domain, feeds)
requirements.txt    # Python dependencies
Makefile            # Build / serve / publish commands
.github/workflows/  # CI: builds and deploys to GitHub Pages on push to main
```

> **Note:** `output/`, `cache/`, and `venv/` are build artifacts / local
> environment and are intentionally git-ignored. Don't commit them — the site is
> regenerated from `content/` + `theme/` on every push.

## Deployment

Hosted on **GitHub Pages** at https://campaigns.healthsites.io.

Deployment is automatic. On every push to `main`, the
`.github/workflows/deploy.yml` workflow:

1. Installs dependencies,
2. Runs `pelican content -s publishconf.py -o output`,
3. Writes the `CNAME` (custom domain) and a `.nojekyll` marker into `output/`,
4. Publishes `output/` to GitHub Pages.

**One-time repo setup (required):**

1. In **Settings → Pages → Build and deployment**, set **Source: GitHub Actions**.
2. In **Settings → Pages → Custom domain**, enter `campaigns.healthsites.io` and
   enable **Enforce HTTPS**.
3. Add a DNS **CNAME** record at your DNS provider:
   `campaigns` → `healthsites.github.io`.

To update the live site, just push to `main`:

```bash
git add .
git commit -m "Update site"
git push origin main
```

## Contributing

1. Fork or clone the repo.
2. Create a feature branch: `git checkout -b feature/cool-thing`
3. Commit: `git commit -m "Add cool thing"`
4. Push: `git push origin feature/cool-thing`
5. Open a Pull Request.

Help build out features, fix bugs, or add translations!

## Support

- Issues: GitHub Issues
- Website: healthsites.io
- Twitter: @healthsitesio

Built with care by the Healthsites community. Let's map health together!
