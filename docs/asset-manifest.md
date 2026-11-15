# Asset manifest

Every brand file used by the site is listed here. `check.py` rejects any image under `/img/` that does not match the allowed paths in `docs/build-spec.md`, section 4:

`emblems/armorial-bearing-(420|840).webp`, `banner/banner-photo.webp`, `og-(en|it|fr|de|es).jpg`, `lockup/(shield|en|it|fr|de|es).svg`, `favicon/*`.

Rules for every asset: use only the official files, never redraw, recolour or approximate an emblem, and never use an image without its rights.

| ID | Asset | Path | Status | Notes |
|---|---|---|---|---|
| EMB-01 | Armorial bearing (institutional emblem) | `static/img/emblems/armorial-bearing-420.webp`, `-840.webp` | Official file, in the repository | Its origin and the master file are not recorded in this repository. Check them before launch. |
| BAN-01 | Banner photograph | `static/img/banner/banner-photo.webp` | Official file, in the repository | Used by the layout as the template sets it. |
| LOCK-SH | Red shield (official), used in the interim lockup | `static/img/lockup/shield.svg` | Made by `python3 tools/make_lockup.py --shield` | An unchanged copy of the official shield group, cropped to the shield. It needs no font. |
| LOCK-TXT | Lockup text | Live text next to the shield | Interim | The layout shows "Sovereign Order of Malta" beside the shield, followed by the full name. This is what the live site does. |
| LOCK-L | Outlined lockups per language | `static/img/lockup/<lang>.svg` (en, it, fr, de, es) | **Open.** Not produced | Needs the licensed Century Gothic Bold font, which is not in the repository and not on the build machine, and the Grand Magistry's approval. |
| OG-1 | Link-preview cards, 1200 × 630 | `static/img/og-<lang>.jpg` (en, it, fr, de, es) | **Open.** Made by `python3 tools/make_og.py` | Needs Playwright and Chromium. The tool is a developer tool, not a build dependency. Until the cards exist, the build leaves out `og:image`. |
| FAV-01 | Favicons | `static/img/favicon/*`, `static/favicon.ico` | Official set, from the template | No change. |
| FNT-01 | Fonts | `static/fonts/*.woff2` | From the template | Asap and EB Garamond, under the SIL Open Font License. Asap is also used for the OG cards. |
| MED-01 | Photographs and documents | `static/media/<YYYY>/<MM>/…` | Imported from www.orderofmalta.int | Rights are inherited from the live site and are not yet confirmed. See below. |
| SOC-01 | Social links | Text labels in the footer and top bar | Text only | No third-party logos. Links come from the live top bar. |

## Files to remove from the scaffold

The Czech files below must not be in the repository. They say "Czech Republic" or show the Czech name:

- `static/img/lockup/cs.svg`, `static/img/lockup/en.svg`, `static/img/lockup/fr.svg`, `static/img/lockup/it.svg`, `static/img/lockup/de.svg`
- `static/img/og-cs.jpg`

The `og-<lang>.jpg` files now in `static/img/` (en, it, fr, de, es) are not yet checked against this site. Replace them with the output of `tools/make_og.py` before launch, or remove them until that tool runs.

## Photographs and documents from the live site

- Source: the media library of www.orderofmalta.int, imported to `static/media/<YYYY>/<MM>/`. Images are converted to WebP. Documents (PDF, DOC, XLS, ZIP) are copied unchanged. A file over 25 MB is not copied, and its link stays on the live site.
- Rights: inherited from the live site. The site does not hold a licence for them. The Grand Magistry must confirm that the Order may use each image.
- Identifiable people: the Grand Magistry must confirm consent for any photograph of an identifiable person, especially of children.
- Video posters: taken from YouTube's public poster images and stored as `static/media/embeds/youtube-<id>.webp`, so that nothing is requested from YouTube before a visitor clicks.

## Not on the site, and not to be created

- Redrawn, recoloured or invented emblems, icons or logos of any organisation.
- Store badges of app stores. The app page uses text links.
- Logos of related organisations.
- Any image without a known source and rights.
