from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Usamos las vistas personalizadas
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('registro/', views.RegistroView.as_view(), name='registro'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    # Aquí puedes añadir vistas de Django (cambio de contraseña, etc.) si las necesitas
    # path('password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    # path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
]
