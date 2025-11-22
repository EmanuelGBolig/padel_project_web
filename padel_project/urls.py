from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # URLs de Core (Home)
    path('', include('core.urls')),
    # URLs de Accounts (Login, Logout, Registro, Perfil)
    path('accounts/', include('accounts.urls')),
    # URLs de Equipos
    path('equipos/', include('equipos.urls')),
    # URLs de Torneos
    path('torneos/', include('torneos.urls')),
]
