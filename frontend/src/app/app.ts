import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <a class="brand" routerLink="/">Projekt auth</a>
      @if (auth.user(); as user) {
        <nav>
          <a routerLink="/account" routerLinkActive="active">Konto</a>
          <a routerLink="/notes" routerLinkActive="active">Notatki</a>
          @if (auth.isAdmin()) {
            <a routerLink="/admin" routerLinkActive="active">Użytkownicy</a>
          }
        </nav>
        <div class="who">
          <span class="email">{{ user.email }}</span>
          <button type="button" (click)="auth.logout()">Wyloguj</button>
        </div>
      }
    </header>
    <main>
      <router-outlet />
    </main>
  `,
})
export class App {
  protected readonly auth = inject(AuthService);
}
