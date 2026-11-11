import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { User, errorMessage } from '../api';
import { AuthService } from '../auth.service';

@Component({
  selector: 'app-account',
  imports: [FormsModule, DatePipe],
  template: `
    @if (auth.user(); as user) {
      <h1>Moje konto</h1>

      <section class="card">
        <dl class="facts">
          <div><dt>E-mail</dt><dd>{{ user.email }}</dd></div>
          <div><dt>Nazwa</dt><dd>{{ user.display_name || '—' }}</dd></div>
          <div>
            <dt>Rola</dt>
            <dd><span class="badge" [class.admin]="user.role === 'admin'">{{ user.role }}</span></dd>
          </div>
          <div><dt>Konto od</dt><dd>{{ user.created_at | date: 'dd.MM.yyyy HH:mm' }}</dd></div>
        </dl>
      </section>

      <div class="grid">
        <section class="card">
          <h2>Nazwa wyświetlana</h2>
          <form (ngSubmit)="saveName()">
            <label>
              Nowa nazwa
              <input type="text" name="displayName" [(ngModel)]="displayName" maxlength="100" />
            </label>
            @if (nameMsg(); as m) {
              <p class="msg" [class.error]="m.error" [class.ok]="!m.error">{{ m.text }}</p>
            }
            <button class="primary" type="submit">Zapisz</button>
          </form>
        </section>

        <section class="card">
          <h2>Zmiana e-maila</h2>
          <form (ngSubmit)="saveEmail()">
            <label>
              Nowy e-mail
              <input type="email" name="newEmail" [(ngModel)]="newEmail" required autocomplete="off" />
            </label>
            <label>
              Obecne hasło
              <input
                type="password"
                name="emailPassword"
                [(ngModel)]="emailPassword"
                required
                autocomplete="current-password"
              />
            </label>
            @if (emailMsg(); as m) {
              <p class="msg" [class.error]="m.error" [class.ok]="!m.error">{{ m.text }}</p>
            }
            <button class="primary" type="submit">Zmień e-mail</button>
          </form>
        </section>

        <section class="card">
          <h2>Zmiana hasła</h2>
          <form (ngSubmit)="savePassword()">
            <label>
              Obecne hasło
              <input
                type="password"
                name="currentPassword"
                [(ngModel)]="currentPassword"
                required
                autocomplete="current-password"
              />
            </label>
            <label>
              Nowe hasło
              <input
                type="password"
                name="newPassword"
                [(ngModel)]="newPassword"
                required
                autocomplete="new-password"
              />
              <small>Co najmniej 8 znaków. Po zmianie trzeba zalogować się ponownie.</small>
            </label>
            @if (passwordMsg(); as m) {
              <p class="msg" [class.error]="m.error" [class.ok]="!m.error">{{ m.text }}</p>
            }
            <button class="primary" type="submit">Zmień hasło</button>
          </form>
        </section>
      </div>
    }
  `,
})
export class Account {
  protected readonly auth = inject(AuthService);
  private readonly http = inject(HttpClient);

  protected readonly displayName = signal(this.auth.user()?.display_name ?? '');
  protected readonly newEmail = signal('');
  protected readonly emailPassword = signal('');
  protected readonly currentPassword = signal('');
  protected readonly newPassword = signal('');

  protected readonly nameMsg = signal<Msg | null>(null);
  protected readonly emailMsg = signal<Msg | null>(null);
  protected readonly passwordMsg = signal<Msg | null>(null);

  protected saveName(): void {
    const display_name = this.displayName().trim() || null;
    this.http.patch<User>('/api/me', { display_name }).subscribe({
      next: (u) => {
        this.auth.user.set(u);
        this.nameMsg.set({ text: 'Zapisano.', error: false });
      },
      error: (err) => this.nameMsg.set({ text: errorMessage(err), error: true }),
    });
  }

  protected saveEmail(): void {
    const body = { new_email: this.newEmail().trim(), current_password: this.emailPassword() };
    if (!body.new_email || !body.current_password) {
      this.emailMsg.set({ text: 'Podaj nowy e-mail i obecne hasło.', error: true });
      return;
    }
    this.http.put<User>('/api/me/email', body).subscribe({
      next: (u) => {
        this.auth.user.set(u);
        this.newEmail.set('');
        this.emailPassword.set('');
        this.emailMsg.set({ text: 'E-mail został zmieniony.', error: false });
      },
      error: (err) => this.emailMsg.set({ text: errorMessage(err), error: true }),
    });
  }

  protected savePassword(): void {
    const body = { current_password: this.currentPassword(), new_password: this.newPassword() };
    if (body.new_password.length < 8) {
      this.passwordMsg.set({ text: 'Nowe hasło musi mieć co najmniej 8 znaków.', error: true });
      return;
    }
    this.http.put('/api/me/password', body).subscribe({
      // serwer unieważnił refresh tokeny, więc kończymy też sesję w przeglądarce
      next: () => this.auth.logout('Hasło zostało zmienione – zaloguj się nowym hasłem.'),
      error: (err) => this.passwordMsg.set({ text: errorMessage(err), error: true }),
    });
  }
}

interface Msg {
  text: string;
  error: boolean;
}
