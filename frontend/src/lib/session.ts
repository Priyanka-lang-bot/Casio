import "server-only";
import { cookies } from "next/headers";
import type { User } from "./api";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

// Asks the backend who is signed in, using the browser's session cookie.
// Returns null if nobody is (or the session expired).
export async function getCurrentUser(): Promise<User | null> {
  const token = (await cookies()).get("casio_session")?.value;
  if (!token) return null;
  const res = await fetch(`${backendUrl}/api/auth/me`, {
    headers: { Cookie: `casio_session=${token}` },
    cache: "no-store",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}
