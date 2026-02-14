from django.urls import path
from . import views

app_name = 'torneos'

urlpatterns = [
    # Vistas de Jugador
    path(
        'finalizados/', views.TorneoFinalizadoListView.as_view(), name='finalizado_list'
    ),
    path(
        'en-juego/', views.TorneoEnJuegoListView.as_view(), name='en_juego_list'
    ),
    path(
        'abiertos/', views.TorneoAbiertoListView.as_view(), name='abierto_list'
    ),
    path('<int:pk>/', views.TorneoDetailView.as_view(), name='detail'),
    path(
        '<int:torneo_pk>/inscribirse/',
        views.InscripcionCreateView.as_view(),
        name='inscribirse',
    ),
    path(
        '<int:torneo_pk>/cancelar-inscripcion/',
        views.InscripcionDeleteView.as_view(),
        name='cancelar_inscripcion',
    ),
    # Vistas de Admin
    path('admin/listado/', views.AdminTorneoListView.as_view(), name='admin_list'),
    path('admin/crear/', views.AdminTorneoCreateView.as_view(), name='admin_crear'),
    path(
        'admin/<int:pk>/editar/',
        views.AdminTorneoUpdateView.as_view(),
        name='admin_editar',
    ),
    path(
        'admin/<int:pk>/eliminar/',
        views.AdminTorneoDeleteView.as_view(),
        name='admin_eliminar',
    ),
    path(
        'admin/<int:pk>/gestionar/',
        views.AdminTorneoManageView.as_view(),
        name='admin_manage',
    ),
    # Carga de resultados (HTMX Modals)
    path(
        'admin/partido/<int:pk>/resultado/',
        views.AdminPartidoUpdateView.as_view(),
        name='admin_partido_resultado',
    ),
    path(
        'admin/grupo/<int:pk>/resultado/',
        views.CargarResultadoGrupoView.as_view(),
        name='cargar_resultado_grupo',
    ),
    path(
        'admin/partido-grupo/<int:pk>/schedule/',
        views.SchedulePartidoGrupoView.as_view(),
        name='schedule_partido_grupo',
    ),
    path(
        'admin/partido/<int:pk>/schedule/',
        views.SchedulePartidoView.as_view(),
        name='schedule_partido',
    ),
    path(
        'admin/partido/<int:pk>/replace-teams/',
        views.ReplacePartidoTeamsView.as_view(),
        name='replace_partido_teams',
    ),
    path(
        'admin/partido-grupo/<int:pk>/replace-teams/',
        views.ReplacePartidoGrupoTeamsView.as_view(),
        name='replace_partido_grupo_teams',
    ),
    path(
        'admin/grupo/<int:pk>/swap-teams/',
        views.SwapGroupTeamsView.as_view(),
        name='swap_group_teams',
    ),
    # Utilidad: Crear torneo de prueba
    path(
        'admin/crear-torneo-prueba/',
        views.crear_torneo_prueba,
        name='crear_torneo_prueba',
    ),
]
