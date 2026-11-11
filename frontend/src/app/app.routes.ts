import { Routes } from '@angular/router';
import { adminGuard, authGuard, guestGuard } from './guards';
import { Account } from './pages/account';
import { Admin } from './pages/admin';
import { Login } from './pages/login';
import { Notes } from './pages/notes';

export const routes: Routes = [
  { path: 'login', component: Login, canActivate: [guestGuard], title: 'Logowanie' },
  { path: 'account', component: Account, canActivate: [authGuard], title: 'Moje konto' },
  { path: 'notes', component: Notes, canActivate: [authGuard], title: 'Notatki' },
  { path: 'admin', component: Admin, canActivate: [adminGuard], title: 'Użytkownicy' },
  { path: '**', redirectTo: 'account' },
];
