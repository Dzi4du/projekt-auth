import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, finalize, firstValueFrom, shareReplay, switchMap, tap } from 'rxjs';
import { Tokens, User } from './api';

const ACCESS_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

/**
 * Stan logowania. Tokeny trzymamy w sessionStorage: przetrwają odświeżenie
 * strony, ale znikają po zamknięciu karty. (Każdy magazyn dostępny z JS jest
 * podatny na XSS – dlatego access token żyje krótko, a refresh token jest
 * rotowany i unieważniany po stronie serwera.)
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly user = signal<User | null>(null);
  readonly isAdmin = computed(() => this.user()?.role === 'admin');
  /** Komunikat pokazywany na ekranie logowania (np. po zmianie hasła). */
  readonly notice = signal('');

  private refreshInFlight?: Observable<Tokens>;

  accessToken(): string | null {
    return sessionStorage.getItem(ACCESS_KEY);
  }

  refreshToken(): string | null {
    return sessionStorage.getItem(REFRESH_KEY);
  }

  /** Wywoływane przy starcie aplikacji: odtwarza sesję po odświeżeniu strony. */
  async restore(): Promise<void> {
    if (!this.accessToken() && !this.refreshToken()) return;
    try {
      await firstValueFrom(this.loadUser());
    } catch {
      this.clearSession();
    }
  }

  register(email: string, password: string, displayName: string): Observable<User> {
    return this.http.post<User>('/auth/register', {
      email,
      password,
      display_name: displayName || null,
    });
  }

  login(email: string, password: string): Observable<User> {
    return this.http.post<Tokens>('/auth/login', { email, password }).pipe(
      tap((t) => this.storeTokens(t)),
      switchMap(() => this.loadUser()),
    );
  }

  loadUser(): Observable<User> {
    return this.http.get<User>('/api/me').pipe(tap((u) => this.user.set(u)));
  }

  /**
   * Wymienia refresh token na nową parę. Serwer rotuje tokeny (stary jest od
   * razu nieważny), więc równoległe żądania muszą współdzielić jedno odświeżenie.
   */
  refresh(): Observable<Tokens> {
    this.refreshInFlight ??= this.http
      .post<Tokens>('/auth/refresh', { refresh_token: this.refreshToken() })
      .pipe(
        tap((t) => this.storeTokens(t)),
        finalize(() => (this.refreshInFlight = undefined)),
        shareReplay(1),
      );
    return this.refreshInFlight;
  }

  logout(notice = ''): void {
    const refresh = this.refreshToken();
    if (refresh) {
      // unieważnia refresh token na serwerze; błąd nie blokuje wylogowania
      this.http.post('/auth/logout', { refresh_token: refresh }).subscribe({ error: () => {} });
    }
    this.clearSession();
    this.notice.set(notice);
    this.router.navigate(['/login']);
  }

  clearSession(): void {
    sessionStorage.removeItem(ACCESS_KEY);
    sessionStorage.removeItem(REFRESH_KEY);
    this.user.set(null);
  }

  private storeTokens(t: Tokens): void {
    sessionStorage.setItem(ACCESS_KEY, t.access_token);
    sessionStorage.setItem(REFRESH_KEY, t.refresh_token);
  }
}
