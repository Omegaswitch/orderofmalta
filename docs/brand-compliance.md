# Brand compliance

**Status: not yet checked against this site.** The rules below come from the project specification (`docs/build-spec.md`, section 4 and the rules in its header) and from the Grand Magistry's own guidance: the *Sovereign Order of Malta Worldwide Communications Policy and Guide* (Rome, February 2025) and the *Guidelines for correct use of the two emblems and of the flags of the Order of Malta* (v3.3, 1 September 2023). The Grand Magistry's graphic theme package also applies.

The checklist must be redone for this site before launch. The template's brand report is not valid here.

## Rules for this site

| # | Rule | How the site meets it | Status |
|---|---|---|---|
| 1 | The four-letter acronym of the Order's name is never written. | `check.py` fails the build if it appears in any built page. Docs, code comments, interface strings and commit messages must not use it either. | Enforced for pages. Other places rely on review. |
| 2 | Only official brand files are used. | `check.py` allows only the paths listed in `docs/asset-manifest.md`. | Enforced by `check.py`. |
| 3 | Emblems are never created, redrawn, recoloured or approximated. | Only the official files are used. The shield is an unchanged copy of the official group. | Complies. |
| 4 | The full official name is shown at first mention. | The full name for each language is in `content/site.json` and is shown beside the lockup. | Complies, subject to the lockup decision below. |
| 5 | Short names follow the Order's own usage. | Short names are in `content/site.json` (`orderShort`). They are taken from the live site's header and footer. | Complies. |
| 6 | Official texts come from the Grand Magistry. | The site contains the texts imported from the live site, not rewritten texts. | Complies. |
| 7 | The lockup. | The banner uses the official outlined lockups with the shield unchanged (see approval 0). | Complies. Approved by the Grand Magistry, 15 Nov 2026. |
| 8 | Social links use text labels only. | No third-party logos. | Complies. |
| 9 | Store badges are not copied. | The app page uses text links. | Complies. |
| 10 | Photographs have confirmed rights and consent. | Not confirmed. | **Open**, see `docs/asset-manifest.md`. |

## Open approvals

0. **Lockups (approved 15 Nov 2026).** The Grand Magistry has approved the banner lockups. EN, IT, FR and DE are line 1 of the template's official outlined lockups with the shield unchanged; ES ("ORDEN DE MALTA") is composed from the official FR and IT letter outlines by `tools/make_lockup_oom.py`. Text alternatives (`lockupAlt` in `content/site.json`) match the lettering shown.

1. **Outlined lockups (approved 15 Nov 2026).** Complied: the outlined lockups for all five languages are in use and the Grand Magistry has approved them (see approval 0). The interim lockup is no longer used.
2. **Which emblem the banner uses.** The guidelines ask for the armorial bearing on institutional sites. The interim banner uses the shield. The Grand Magistry should decide.
3. **Colour and display type.** The design system comes from the template (`DESIGN.md`). The template's brand report lists two points that the Grand Magistry has not yet answered: the canonical red value, and whether headings should use a serif font. These apply to this site until answered.
4. **Link-preview cards.** `tools/make_og.py` must run to produce `og-<lang>.jpg` in all five languages.
5. **Translations.** The interface strings in `content/i18n.json` and the translated text should be reviewed by a native speaker. Order terms should be checked against the Grand Magistry's usage.
6. **Approval of this rebuild.** The launch needs the Grand Magistry's approval. See `docs/deployment.md`.
