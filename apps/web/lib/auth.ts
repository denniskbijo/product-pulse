export type Role = "admin" | "user";

export type Session = {
  accessToken: string;
  username: string;
  role: Role;
};

const STORAGE_KEY = "product-pulse-session";

export function loadSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Session;
    if (!data.accessToken || !data.username || !data.role) return null;
    return data;
  } catch {
    return null;
  }
}

export function saveSession(session: Session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY);
}

export function isAdmin(session: Session | null): boolean {
  return session?.role === "admin";
}
