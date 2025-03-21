import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { UserAuthServiceService } from '../../services/UserAuthService.service';
import { ProfileService, UserProfile } from '../../services/ProfileService.service';
import { CommonModule } from '@angular/common';
import { NAVIGATION_ROUTES } from '../../utils/constants';
import { BookSearchComponent } from '../book-search/book-search.component';
import { Book } from '../../services/BookSearchService.service';
import { FavoriteService, FavoriteBook } from '../../services/FavoriteService.service';
import { ToastrService } from 'ngx-toastr';  // ✅ Importar ToastrService
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-home',
  standalone: true,
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css'],
  imports: [CommonModule, BookSearchComponent, FormsModule],
})
export class HomeComponent implements OnInit {
  isAuthenticated: boolean = false;
  userProfile: UserProfile | null = null;
  searchedUsername: string = '';


  constructor(
    private userAuthService: UserAuthServiceService,
    private profileService: ProfileService,
    private router: Router,
    private favoriteService: FavoriteService,
    private toastr: ToastrService // ✅ Inyectar ToastrService
  ) {}

  ngOnInit(): void {
    this.isAuthenticated = this.userAuthService.isAuthenticated();
    if (this.isAuthenticated) {
      this.loadUserProfile();
      this.checkPendingFavorite();
    }
  }

  private loadUserProfile(): void {
    this.profileService.getUserProfile().subscribe({
      next: (profile: UserProfile) => {
        this.userProfile = profile;
      },
      error: (error) => {
        console.error('⚠️ Error loading profile:', error);
      }
    });
  }

  navigateToPublicProfile() {
    if (this.searchedUsername.trim()) {
      this.router.navigate([`/user/${this.searchedUsername.trim()}`]);
    }
  }

  get username(): string {
    return localStorage.getItem('username') || 'Usuario';
  }

  logout() {
    this.userAuthService.logout();
    this.router.navigate([NAVIGATION_ROUTES.LOGIN]);
  }

  navigateToLogin() {
    this.router.navigate([NAVIGATION_ROUTES.LOGIN]);
  }

  navigateToRegister() {
    this.router.navigate([NAVIGATION_ROUTES.REGISTER]);
  }

  navigateToFavoriteList() {
    this.router.navigate([NAVIGATION_ROUTES.FAVORITES]);
  }

  navigateToProfile() {
    this.router.navigate([NAVIGATION_ROUTES.PROFILE]);
  }

  // ✅ Método que revisa y guarda el pending favorite con toast
  private checkPendingFavorite() {
    const pendingBookData = localStorage.getItem('pendingFavoriteBook');
    if (pendingBookData) {
      const pendingBook: Book = JSON.parse(pendingBookData);

      const favoriteBook: FavoriteBook = {
        book_key: pendingBook.book_key,
        title: pendingBook.title,
        author: pendingBook.author || '',
        isbn: pendingBook.isbn || undefined,
        genres: Array.isArray(pendingBook.genres) ? pendingBook.genres : [],
        first_publish_year: pendingBook.first_publish_year || undefined,
        cover_url: pendingBook.cover_url || undefined,
        review: '',
        rating: 0,
      };

      this.favoriteService.addFavorite(favoriteBook).subscribe({
        next: () => {
          console.log(`✅ Libro '${favoriteBook.title}' añadido automáticamente después del login.`);
          localStorage.removeItem('pendingFavoriteBook');
          this.toastr.success(
            `'${favoriteBook.title}' se ha añadido a tus favoritos ⭐`,
            'Libro añadido'
          );
        },
        error: (err: any) => {
          console.error('⚠️ Error añadiendo favorito post-login:', err);
          localStorage.removeItem('pendingFavoriteBook');
          this.toastr.error(
            'No se pudo añadir el libro automáticamente.',
            'Error'
          );
        },
      });
    }
  }
}
