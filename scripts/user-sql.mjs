// Prints SQL that adds a co-worker, to paste into the Neon SQL editor (no database connection needed):
//   node scripts/user-sql.mjs "Jane Smith" jane@example.org 'a-long-password' [editor|admin|owner]
import { hashPassword } from "better-auth/crypto";
import { randomUUID } from "crypto";

const [name, email, password, role = "editor"] = process.argv.slice(2);
if (!name || !email || !password || password.length < 12 || !["editor", "admin", "owner"].includes(role)) {
  console.error('usage: node scripts/user-sql.mjs "Name" email password(12+ chars) [editor|admin|owner]'); process.exit(1);
}
const q = (s) => "'" + String(s).replace(/'/g, "''") + "'";
const id = randomUUID(), hash = await hashPassword(password);
console.log(`insert into "user" ("id","name","email","emailVerified","role") values (${q(id)},${q(name)},${q(email.trim().toLowerCase())},true,${q(role)});
insert into "account" ("id","accountId","providerId","userId","password") values (${q(randomUUID())},${q(id)},'credential',${q(id)},${q(hash)});`);
