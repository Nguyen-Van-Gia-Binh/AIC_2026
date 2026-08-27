// session.ts — sinh 1 session_id (UUID) luu trong localStorage, dung chung cho toan bo query
// hang doi cua trinh duyet nay (xem scripts/api/state.py o backend).
const KEY = "aic_session_id";

export function getSessionId(): string {
  let id = localStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(KEY, id);
  }
  return id;
}
