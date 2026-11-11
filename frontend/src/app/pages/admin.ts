import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { Role, User, errorMessage } from '../api';
import { AuthService } from '../auth.service';

@Component({
  selector: 'app-admin',
  imports: [DatePipe],
  template: `
    <h1>Użytkownicy</h1>
    <p class="lead">Panel administratora: nadawanie ról i usuwanie kont.</p>

    @if (error()) {
      <p class="msg error">{{ error() }}</p>
    }

    <section class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>E-mail</th>
            <th>Nazwa</th>
            <th>Rola</th>
            <th>Konto od</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          @for (u of users(); track u.id) {
            <tr>
              <td>{{ u.id }}</td>
              <td>{{ u.email }}</td>
              <td>{{ u.display_name || '—' }}</td>
              <td><span class="badge" [class.admin]="u.role === 'admin'">{{ u.role }}</span></td>
              <td>{{ u.created_at | date: 'dd.MM.yyyy' }}</td>
              <td class="actions">
                @if (u.id === auth.user()?.id) {
                  <span class="muted">to Ty</span>
                } @else {
                  <button type="button" (click)="setRole(u, u.role === 'admin' ? 'user' : 'admin')">
                    {{ u.role === 'admin' ? 'Odbierz admina' : 'Nadaj admina' }}
                  </button>
                  <button type="button" class="danger" (click)="remove(u)">Usuń</button>
                }
              </td>
            </tr>
          } @empty {
            <tr><td colspan="6" class="muted">{{ loading() ? 'Wczytywanie…' : 'Brak użytkowników.' }}</td></tr>
          }
        </tbody>
      </table>
    </section>

    <div class="pager">
      <button type="button" [disabled]="page() === 0" (click)="load(page() - 1)">← Poprzednie</button>
      <span class="muted">Strona {{ page() + 1 }}</span>
      <button type="button" [disabled]="users().length < pageSize" (click)="load(page() + 1)">
        Następne →
      </button>
    </div>
  `,
})
export class Admin {
  protected readonly auth = inject(AuthService);
  private readonly http = inject(HttpClient);

  protected readonly pageSize = 20;
  protected readonly users = signal<User[]>([]);
  protected readonly page = signal(0);
  protected readonly loading = signal(true);
  protected readonly error = signal('');

  constructor() {
    this.load(0);
  }

  protected load(page: number): void {
    this.loading.set(true);
    const params = { limit: this.pageSize, offset: page * this.pageSize };
    this.http.get<User[]>('/api/users', { params }).subscribe({
      next: (users) => {
        this.users.set(users);
        this.page.set(page);
        this.loading.set(false);
        this.error.set('');
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  protected setRole(user: User, role: Role): void {
    this.http.put<User>(`/api/users/${user.id}/role`, { role }).subscribe({
      next: (updated) => {
        this.users.update((list) => list.map((u) => (u.id === updated.id ? updated : u)));
        this.error.set('');
      },
      error: (err) => this.error.set(errorMessage(err)),
    });
  }

  protected remove(user: User): void {
    if (!confirm(`Usunąć konto ${user.email}? Tej operacji nie można cofnąć.`)) return;
    this.http.delete(`/api/users/${user.id}`).subscribe({
      next: () => this.load(this.page()),
      error: (err) => this.error.set(errorMessage(err)),
    });
  }
}
