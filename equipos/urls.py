from django.urls import path
from . import views

app_name = 'equipos'

urlpatterns = [
    # Vistas de Autocompletado (NUEVA)
    path(
        'autocomplete/jugadores/',
        views.JugadorAutocomplete.as_view(),
        name='jugador_autocomplete',
    ),
    # Vistas de Jugador
    path('mi-equipo/', views.MiEquipoDetailView.as_view(), name='mi_equipo'),
    path('crear/', views.EquipoCreateView.as_view(), name='crear'),
    path('disolver/', views.EquipoDeleteView.as_view(), name='disolver'),
    # Vistas de Admin
    path('admin/listado/', views.AdminEquipoListView.as_view(), name='admin_list'),
]
