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
    path('completar-perfil/', views.CompleteGoogleProfileView.as_view(), name='complete_google_profile'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    path('jugador/<int:pk>/', views.PublicProfileView.as_view(), name='detalle'),
    path('rankings/', views.RankingJugadoresListView.as_view(), name='rankings_jugadores'),
    path('organizador/<int:pk>/', views.OrganizacionDetailView.as_view(), name='organizador_detalle'),
    path('organizador/<int:pk>/programacion/', views.OrganizacionProgramacionView.as_view(), name='organizacion_programacion'),
    path('organizadores/', views.OrganizacionListView.as_view(), name='organizador_list'),
    # Gestión de Organización
    path('organizacion/ajustes/', views.OrganizacionSettingsView.as_view(), name='organizacion_settings'),
    path('organizacion/sponsors/', views.OrganizacionSponsorsView.as_view(), name='organizacion_sponsors'),
    path('organizacion/sponsors/<int:pk>/editar/', views.SponsorUpdateView.as_view(), name='editar_sponsor'),
    path('organizacion/sponsors/<int:pk>/delete/', views.SponsorDeleteView.as_view(), name='eliminar_sponsor'),
    path('organizacion/jugador-dummy/crear/', views.DummyUserCreationView.as_view(), name='crear_dummy_user'),
    
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
