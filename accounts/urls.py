from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Usamos las vistas personalizadas
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('registro/', views.RegistroView.as_view(), name='registro'),
    path('verificar-email/', views.VerifyEmailView.as_view(), name='verificar_email'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    path('jugador/<int:pk>/', views.PublicProfileView.as_view(), name='detalle'),
    path('rankings/', views.RankingJugadoresListView.as_view(), name='rankings_jugadores'),
    path('rankings/', views.RankingJugadoresListView.as_view(), name='rankings_jugadores'),
    
    # Rutas de recuperación de contraseña (Django Auth)
    # Rutas de recuperación de contraseña (Explícitas para corregir namespace)
    path('password_reset/', auth_views.PasswordResetView.as_view(
        success_url=reverse_lazy('accounts:password_reset_done'),
        email_template_name='registration/password_reset_email.html'
    ), name='password_reset'),
    
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        success_url=reverse_lazy('accounts:password_reset_complete')
    ), name='password_reset_confirm'),
    
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
