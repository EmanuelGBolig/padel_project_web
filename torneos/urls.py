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
        'mis-torneos/', views.MisTorneosView.as_view(), name='mis_torneos'
    ),
    path(
        'abiertos/', views.TorneoAbiertoListView.as_view(), name='abierto_list'
    ),
    path('ciudad/<str:ciudad>/', views.TorneoPorCiudadView.as_view(), name='ciudad'),
    # Circuitos (TP-12)
    path('circuitos/', views.CircuitoListView.as_view(), name='circuito_list'),
    path('circuito/<int:pk>/', views.CircuitoDetailView.as_view(), name='circuito_detail'),
    # Americano / Mexicano (TP-09)
    path('americanos/', views.AmericanoListView.as_view(), name='americano_list'),
    path('americano/crear/', views.AmericanoCreateView.as_view(), name='americano_crear'),
    path('americano/sumarse/<str:codigo>/', views.AmericanoJoinView.as_view(), name='americano_join'),
    path('americano/<int:pk>/', views.AmericanoDetailView.as_view(), name='americano_detail'),
    path('americano/<int:pk>/gestionar/', views.AmericanoManageView.as_view(), name='americano_manage'),
    path('<int:pk>/', views.TorneoDetailView.as_view(), name='detail'),
    path('<int:pk>/programacion/', views.TorneoProgramacionView.as_view(), name='programacion'),
    path('<int:pk>/vivo/', views.TorneoVivoView.as_view(), name='vivo'),
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
    path('admin/preview-estructura/', views.PreviewEstructuraView.as_view(), name='admin_preview_estructura'),
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
    path(
        'admin/<int:pk>/reemplazar-equipo/',
        views.TorneoReplaceTeamView.as_view(),
        name='torneo_reemplazar_equipo',
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
    # Redirección de seguridad para el path base /torneos/
    path('', lambda r: redirect('torneos:abierto_list'), name='base_redirect'),
]

from django.shortcuts import redirect

