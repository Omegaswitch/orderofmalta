// Better Auth for /pridat-aktualitu/: e-mail + password sign-in, sessions and roles (editor/admin) kept in Postgres.
// Files starting with "_" are not routes on Vercel; api/auth/[...all].js serves this at /api/auth/*.
// Env: DATABASE_URL (Postgres, e.g. Neon), BETTER_AUTH_SECRET (long random string), BETTER_AUTH_URL (site origin).
// Nobody can sign themselves up: an admin adds co-workers with `npm run auth:user`.
import { betterAuth } from "better-auth";
import { admin } from "better-auth/plugins";
import { createAccessControl } from "better-auth/plugins/access";
import { adminAc, defaultStatements } from "better-auth/plugins/admin/access";
import pg from "pg";

// Roles: "owner" may also add, remove and reset people (chosen admins only); "admin" may change any post; "editor" their own.
const ac = createAccessControl(defaultStatements);
const roles = { owner: ac.newRole(adminAc.statements), admin: ac.newRole({ user: [], session: [] }), editor: ac.newRole({ user: [], session: [] }) };

export const auth = betterAuth({
  database: new pg.Pool({ connectionString: process.env.DATABASE_URL }),
  emailAndPassword: { enabled: true, disableSignUp: true, minPasswordLength: 10 },
  session: { expiresIn: 12 * 3600, updateAge: 3600 },
  rateLimit: { enabled: true, window: 60, max: 10 },
  plugins: [admin({ ac, roles, defaultRole: "editor", adminRoles: ["owner"] })],
});
