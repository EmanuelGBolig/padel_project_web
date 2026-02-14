from django.urls import path, include
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
    path('', include('django.contrib.auth.urls')),
]
