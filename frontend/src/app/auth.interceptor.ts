import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

function withToken(req: HttpRequest<unknown>, token: string | null): HttpRequest<unknown> {
  return token ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : req;
}

/**
 * Dokleja nagłówek "Authorization: Bearer <JWT>" do żądań /api/...
 * Gdy access token wygaśnie (401), jednorazowo odświeża go refresh tokenem
 * i ponawia żądanie; jeśli to się nie uda – wylogowuje.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // /auth/login, /auth/register, /auth/refresh nie potrzebują tokenu
  if (req.url.startsWith('/auth/')) return next(req);

  return next(withToken(req, auth.accessToken())).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status !== 401 || !auth.refreshToken()) return throwError(() => err);
      return auth.refresh().pipe(
        catchError((refreshErr) => {
          auth.clearSession();
          auth.notice.set('Sesja wygasła – zaloguj się ponownie.');
          router.navigate(['/login']);
          return throwError(() => refreshErr);
        }),
        switchMap(() => next(withToken(req, auth.accessToken()))),
      );
    }),
  );
};
