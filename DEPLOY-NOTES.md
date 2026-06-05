# Deploy drop-in — read me first

This folder mirrors your repo root. To apply it, copy its contents into the
`campaign-site-2026` repo, overwriting when prompted:

```
deploy-drop-in/
├── .github/workflows/deploy.yml      → new: CI that builds & deploys to Pages
├── CNAME                             → new: custom domain for Pages
├── README.md                         → replaces the stale README
├── publishconf.py                    → replaces (fixes a syntax bug — see below)
└── theme/static/images/              → optimized images (overwrite the originals)
```

---

## 1. Images — 37 MB → ~2.7 MB (used) 

Every photo was resized to a 1600px long edge and re-compressed. The 9 images
your site actually references drop from **9.8 MB → 2.7 MB** with no visible quality
loss at display size. Just overwrite `theme/static/images/` with this folder's copy.

### Delete these UNUSED images (≈26 MB) — biggest size win

Nothing in `content/` or `theme/templates/` references these. Removing them is the
single largest reduction. (Optimized copies are included in case you wire them up
later; delete the repo originals either way.)

```
theme/static/images/1-geomatica.jpg
theme/static/images/1-lamine-ndiaye.jpg
theme/static/images/241202-OCHA-2.jpg
theme/static/images/35094142223_47894c5a86_k.jpg
theme/static/images/35771827381_b11b0a96ad_k (1).jpg
theme/static/images/Intrahealth-PATH-OCHA-Swiss-TPH11.jpg
theme/static/images/img_20190715_104015790~2_48290610307_o.jpg
theme/static/images/img_20190723_131140174_48356055966_o.jpg
theme/static/images/20190717_093311_50396810148_o.jpg
theme/static/images/20190717_115957_50397639862_o.jpg
theme/static/images/20190717_125126_50397510116_o.jpg
theme/static/images/20190717_144533_50397498141_o.jpg
theme/static/images/20190717_151110_50396810928_o.jpg
theme/static/images/20190718_140708_50397478541_o.jpg
theme/static/images/1-healthsites-emergency-health.png
theme/static/images/The-African-Renaissance-Monument.png
theme/static/images/campaigns/senegal/photos/lamine-OSM-red-cross.png
theme/static/images/campaigns/senegal/maps/map-of-senegal-districts.png
```

The 9 images that ARE used (keep these): `healthsites-saint-louis-2019.jpg`,
`1-OSM-Senegal.jpg`, `img_20190723_124138100_48355995842_o.jpg`,
`healthsites-workshop-ama.jpg`, `1-infirmary.jpg`, `1-ambulance.jpg`,
`1-230209-healthsites-SL-hospital.png`, `validated-healthsites-saint-louis1.png`,
`senegal-regions.png`.

### Optional: shrink the homepage screenshot (871 KB → 194 KB)

`1-230209-healthsites-SL-hospital.png` is a screenshot that doesn't compress as PNG.
I included a JPG version (`1-230209-healthsites-SL-hospital.jpg`, 194 KB). To use it,
edit **`theme/templates/index.html` line 193** and change the extension:

```
- <img src="/theme/images/1-230209-healthsites-SL-hospital.png" ...>
+ <img src="/theme/images/1-230209-healthsites-SL-hospital.jpg" ...>
```

If you don't make this edit, the PNG is used (still fine) and you can delete the
unused `.jpg`.

> **Don't commit `output/`, `cache/`, or `venv/`.** Your `.gitignore` already
> excludes them. They make the folder look huge on disk, but they aren't part of
> the repo — the site is rebuilt from source on every push.

---

## 2. publishconf.py — fixes a build-breaking bug

The original last line was missing its closing quote:

```python
I18N_SUBSITES['ar']['SITEURL'] = f'{SITEURL}/ar      # ← unterminated string
```

This raises a `SyntaxError` and **the production build cannot run** until it's fixed.
The replacement `publishconf.py` corrects it.

---

## 3. One-time GitHub Pages setup

1. **Settings → Pages → Build and deployment → Source:** select **GitHub Actions**.
2. **Settings → Pages → Custom domain:** enter `campaigns.healthsites.io`, save,
   then tick **Enforce HTTPS** once the certificate is issued.
3. **DNS** (at your domain provider): add a `CNAME` record
   `campaigns → healthsites.github.io`.

After that, every push to `main` builds and publishes automatically. You can also
trigger it manually from the **Actions** tab ("Run workflow").

The workflow builds with `publishconf.py` (so `SITEURL = https://campaigns.healthsites.io`),
writes the `CNAME` + a `.nojekyll` marker into `output/`, and deploys it.
