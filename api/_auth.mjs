// Better Auth for the staff editor (/editor/): e-mail + password sign-in, sessions and roles (editor/admin/owner) kept in Postgres.
// Files starting with "_" are not routes on Vercel; api/auth.js serves this at /api/auth/* (vercel.json rewrite).
// Env: DATABASE_URL (Postgres, e.g. Neon), BETTER_AUTH_SECRET (long random string, never in code),
//      BETTER_AUTH_URL (the production origin, e.g. https://www.orderofmalta.int),
//      optional BETTER_AUTH_TRUSTED_ORIGINS (more origins, comma separated).
// Vercel preview and branch URLs (VERCEL_URL, VERCEL_BRANCH_URL, VERCEL_PROJECT_PRODUCTION_URL) are trusted automatically,
// so sign-in also works on a preview deployment. Anything else is refused by Better Auth's origin check.
// Nobody can sign themselves up: an owner adds co-workers in the editor, or an admin uses `npm run auth:user`.
import { betterAuth } from "better-auth";
import { admin } from "better-auth/plugins";
import { createAccessControl } from "better-auth/plugins/access";
import { adminAc, defaultStatements } from "better-auth/plugins/admin/access";
import pg from "pg";

// Roles: "owner" may also add, remove and reset people (chosen admins only); "admin" may change any post; "editor" their own.
const ac = createAccessControl(defaultStatements);
const roles = { owner: ac.newRole(adminAc.statements), admin: ac.newRole({ user: [], session: [] }), editor: ac.newRole({ user: [], session: [] }) };

const origin = (v) => { try { return v ? new URL(/^https?:\/\//.test(v) ? v : `https://${v}`).origin : null; } catch { return null; } };
const env = process.env;
const trustedOrigins = [...new Set([env.BETTER_AUTH_URL, env.VERCEL_URL, env.VERCEL_BRANCH_URL, env.VERCEL_PROJECT_PRODUCTION_URL,
  ...String(env.BETTER_AUTH_TRUSTED_ORIGINS || "").split(/[,\s]+/)].map(origin).filter(Boolean))];

export const auth = betterAuth({
  database: new pg.Pool({ connectionString: env.DATABASE_URL }),
  baseURL: origin(env.BETTER_AUTH_URL) || undefined,  // falls back to the request's own origin when unset
  trustedOrigins,
  emailAndPassword: { enabled: true, disableSignUp: true, minPasswordLength: 12, maxPasswordLength: 128 },
  session: { expiresIn: 12 * 3600, updateAge: 3600 },
  rateLimit: { enabled: true, window: 60, max: 10 },
  advanced: { useSecureCookies: true, defaultCookieAttributes: { sameSite: "strict", httpOnly: true } },
  plugins: [admin({ ac, roles, defaultRole: "editor", adminRoles: ["owner"] })],
});
