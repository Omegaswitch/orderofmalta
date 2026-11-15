// /api/auth/* — Better Auth's sign-in, sign-out, session and user endpoints (configured in api/_auth.mjs).
// Plain Vercel functions have no catch-all routes, so vercel.json rewrites /api/auth/<path> here as ?__p=<path>.
module.exports = async (req, res) => {
  const u = new URL(req.url, "http://local");
  const p = (u.searchParams.get("__p") ?? u.pathname.replace(/^\/api\/auth\/?/, "")).replace(/^\/+|\/+$/g, "");
  u.searchParams.delete("__p");
  req.url = "/api/auth/" + p + u.search;
  const [{ auth }, { toNodeHandler }] = await Promise.all([import("./_auth.mjs"), import("better-auth/node")]);
  return toNodeHandler(auth)(req, res);
};
