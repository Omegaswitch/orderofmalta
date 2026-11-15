// Adds a co-worker who may publish:  node scripts/add-user.mjs "Jane Smith" jane@example.org 'a-long-password' [editor|admin|owner]
// Needs DATABASE_URL and BETTER_AUTH_SECRET; run `npm run auth:migrate` once first to create the tables.
import { auth } from "../api/_auth.mjs";

const [name, email, password, role = "editor"] = process.argv.slice(2);
if (!name || !email || !password || password.length < 12 || !["editor", "admin", "owner"].includes(role)) {
  console.error('usage: node scripts/add-user.mjs "Name" email password(12+ chars) [editor|admin|owner]');
  process.exit(1);
}
const { user } = await auth.api.createUser({ body: { name, email, password, role } });
console.log(`added ${user.name} <${user.email}> as ${role}`);
process.exit(0);
