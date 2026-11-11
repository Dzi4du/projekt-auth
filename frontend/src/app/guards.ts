import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

// Uwaga: strażnicy tylko ukrywają ekrany. Prawdziwa kontrola dostępu jest
// w API (401 bez tokenu, 403 bez roli admina).

export const authGuard: CanActivateFn = () =>
  inject(AuthService).user() ? true : inject(Router).createUrlTree(['/login']);

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  if (!auth.user()) return inject(Router).createUrlTree(['/login']);
  return auth.isAdmin() ? true : inject(Router).createUrlTree(['/account']);
};

export const guestGuard: CanActivateFn = () =>
  inject(AuthService).user() ? inject(Router).createUrlTree(['/account']) : true;
