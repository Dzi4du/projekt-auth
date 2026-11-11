import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { switchMap } from 'rxjs';
import { errorMessage } from '../api';
import { AuthService } from '../auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <section class="card narrow">
      <div class="tabs">
        <button type="button" [class.active]="mode() === 'login'" (click)="switchMode('login')">
          Logowanie
        </button>
        <button type="button" [class.active]="mode() === 'register'" (click)="switchMode('register')">
          Rejestracja
        </button>
      </div>

      @if (auth.notice()) {
        <p class="msg info">{{ auth.notice() }}</p>
      }

      <form (ngSubmit)="submit()">
        <label>
          E-mail
          <input type="email" name="email" [(ngModel)]="email" required autocomplete="username" />
        </label>
        <label>
          Hasło
          <input
            type="password"
            name="password"
            [(ngModel)]="password"
            required
            [attr.autocomplete]="mode() === 'login' ? 'current-password' : 'new-password'"
          />
          @if (mode() === 'register') {
            <small>Co najmniej 8 znaków.</small>
          }
        </label>
        @if (mode() === 'register') {
          <label>
            Nazwa wyświetlana (opcjonalnie)
            <input type="text" name="displayName" [(ngModel)]="displayName" maxlength="100" />
          </label>
        }

        @if (error()) {
          <p class="msg error">{{ error() }}</p>
        }

        <button class="primary" type="submit" [disabled]="busy()">
          {{ mode() === 'login' ? 'Zaloguj się' : 'Załóż konto' }}
        </button>
      </form>
    </section>
  `,
})
export class Login {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly mode = signal<'login' | 'register'>('login');
  protected readonly email = signal('');
  protected readonly password = signal('');
  protected readonly displayName = signal('');
  protected readonly error = signal('');
  protected readonly busy = signal(false);

  protected switchMode(mode: 'login' | 'register'): void {
    this.mode.set(mode);
    this.error.set('');
  }

  protected submit(): void {
    const email = this.email().trim();
    const password = this.password();
    if (!email || !password) {
      this.error.set('Podaj e-mail i hasło.');
      return;
    }
    if (this.mode() === 'register' && password.length < 8) {
      this.error.set('Hasło musi mieć co najmniej 8 znaków.');
      return;
    }

    this.busy.set(true);
    this.error.set('');
    const login$ = this.auth.login(email, password);
    const request$ =
      this.mode() === 'register'
        ? this.auth.register(email, password, this.displayName().trim()).pipe(switchMap(() => login$))
        : login$;

    request$.subscribe({
      next: () => {
        this.auth.notice.set('');
        this.router.navigate(['/account']);
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.busy.set(false);
      },
    });
  }
}
