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
    # Rankings
    path('rankings/', views.RankingListView.as_view(), name='rankings'),
    # Vistas de Admin
    path('admin/listado/', views.AdminEquipoListView.as_view(), name='admin_list'),
    
    # Invitaciones
    path('invitacion/<int:pk>/aceptar/', views.AceptarInvitacionView.as_view(), name='aceptar_invitacion'),
    path('invitacion/<int:pk>/rechazar/', views.RechazarInvitacionView.as_view(), name='rechazar_invitacion'),
    
    # Organizador
    path('organizador/crear-pareja/', views.OrganizadorEquipoCreateView.as_view(), name='crear_pareja'),
    path(
        'autocomplete/organizador-jugadores/',
        views.OrganizadorJugadorAutocomplete.as_view(),
        name='organizador_jugador_autocomplete',
    ),
]
