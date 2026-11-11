import { HttpErrorResponse } from '@angular/common/http';

export type Role = 'user' | 'admin';

export interface User {
  id: number;
  email: string;
  display_name: string | null;
  role: Role;
  created_at: string;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Note {
  id: number;
  content: string;
  created_at: string;
}

/** Zamienia błąd z API (FastAPI: {"detail": ...}) na komunikat dla użytkownika. */
export function errorMessage(err: unknown): string {
  const e = err as HttpErrorResponse;
  const detail = e?.error?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  if (e?.status === 0) return 'Brak połączenia z serwerem';
  return `Wystąpił błąd (${e?.status ?? '?'})`;
}
