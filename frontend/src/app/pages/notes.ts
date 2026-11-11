import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Note, errorMessage } from '../api';

@Component({
  selector: 'app-notes',
  imports: [FormsModule, DatePipe],
  template: `
    <h1>Notatki</h1>
    <p class="lead">Prywatne dane użytkownika – API zwraca tylko notatki właściciela tokenu.</p>

    <section class="card">
      <form (ngSubmit)="add()">
        <label>
          Nowa notatka
          <textarea name="content" rows="3" maxlength="2000" [(ngModel)]="content" required></textarea>
        </label>
        @if (error()) {
          <p class="msg error">{{ error() }}</p>
        }
        <button class="primary" type="submit">Dodaj</button>
      </form>
    </section>

    @if (loading()) {
      <p class="muted">Wczytywanie…</p>
    } @else {
      <ul class="notes">
        @for (note of notes(); track note.id) {
          <li class="card">
            <p>{{ note.content }}</p>
            <small>{{ note.created_at | date: 'dd.MM.yyyy HH:mm' }}</small>
          </li>
        } @empty {
          <li class="muted">Nie masz jeszcze żadnych notatek.</li>
        }
      </ul>
    }
  `,
})
export class Notes {
  private readonly http = inject(HttpClient);

  protected readonly notes = signal<Note[]>([]);
  protected readonly loading = signal(true);
  protected readonly content = signal('');
  protected readonly error = signal('');

  constructor() {
    this.http.get<Note[]>('/api/notes').subscribe({
      next: (notes) => {
        this.notes.set(notes.reverse()); // najnowsze na górze
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  protected add(): void {
    const content = this.content().trim();
    if (!content) return;
    this.http.post<Note>('/api/notes', { content }).subscribe({
      next: (note) => {
        this.notes.update((list) => [note, ...list]);
        this.content.set('');
        this.error.set('');
      },
      error: (err) => this.error.set(errorMessage(err)),
    });
  }
}
