# Legal and privacy compliance

**Status: not reviewed for this site. Not legal advice.** The Order's own legal advisers must review this document. The legal review of the template site is not valid for this site and has been removed.

## Operator details

The live footer gives the following (`docs/build-spec.md`, section 4):

- Magistral Palace, Via Condotti, 68, 00187 Rome, Italy
- Telephone: +39.06.67581.1
- E-mail: `info@orderofmalta.int`; history and bibliography: `info.biblio@orderofmalta.int`

No company number, registration number or named person is shown. None is in the sources. **Open:** the legal name and status of the entity that operates the site, and whether any registration details must be shown.

## Points by topic

| Topic | What the site does | Status |
|---|---|---|
| Privacy notice | Imported from the live site. The text describes the old site. | **Open.** Marked `"status": "approval"`. It needs rewriting for this site and approval by the Order. |
| Cookie policy | Imported from the live site. The text describes the old site. | **Open.** Marked `"status": "approval"`. The site sets no cookies, so the text needs review. |
| Cookies and tracking | No cookies are set by the site. No analytics. Google Tag Manager is dropped. | No cookie banner is built. Confirm with counsel that none is needed. |
| Video consent | After "Always load videos", the choice is stored in `localStorage` (`oom-embed-consent`). It is not a cookie and is not sent anywhere. | **Open.** Confirm that this needs no disclosure. |
| Third-party videos | YouTube (`youtube-nocookie.com`) and Vimeo load only after a click. | Complies with the design. The privacy notice must say so. |
| Data-protection request form (`/gdpr/`) | Sends the request by e-mail through Resend to the address in `GDPR_TO`. The site stores nothing. | **Open.** The recipient address is not set in the code and must be provided. Confirm Resend's role as a processor, and where the e-mail is kept. |
| Staff accounts | E-mail and password of each editor, in Postgres through Better Auth. | **Open.** Set how long these records are kept, and say so in the notice to staff. |
| Hosting logs | Hosted on Vercel, which keeps server logs. | **Open.** Describe in the privacy notice. |
| Photographs of people | Imported from the live site. | **Open.** Confirm consent for each identifiable person, especially children. |
| Copyright of imported text and images | Inherited from the live site. | **Open.** Confirm the Order's rights to each image and text. |
| Fonts | Asap and EB Garamond under the SIL Open Font License. | Complies. |
| Accessibility | Target WCAG 2.2 AA, as in the template. | Not yet tested. An accessibility statement is optional. Confirm the target. |

## Open items

1. Operator's legal name, status and any required registration details.
2. Rewrite and approval of the privacy notice and the cookie policy for this site.
3. The address that receives data-protection requests (`GDPR_TO`).
4. Whether the video consent in `localStorage` needs disclosure.
5. Retention of staff account data and of e-mail sent through the form.
6. Rights to imported photographs and text, and consent for identifiable people.
