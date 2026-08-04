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
    # Placas para redes (9:16)
    path('placa/', views.PlacaView.as_view(), name='placa_app'),
    path('<int:pk>/placa/', views.PlacaView.as_view(), name='placa'),
    # Placas nuevas: ficha del jugador y resultado de un partido.
    path('placa/jugador/<int:pk>/', views.PlacaJugadorView.as_view(), name='placa_jugador'),
    path(
        'placa/partido/<str:tipo>/<int:pk>/',
        views.PlacaResultadoView.as_view(),
        name='placa_resultado',
    ),
    # Circuitos (TP-12)
    path('circuitos/', views.CircuitoListView.as_view(), name='circuito_list'),
    path('circuito/<int:pk>/', views.CircuitoDetailView.as_view(), name='circuito_detail'),
    # Administración de circuitos (el motor ya existía; faltaba la pantalla)
    path('admin/circuitos/', views.CircuitoAdminListView.as_view(), name='circuito_admin_list'),
    path('admin/circuitos/nuevo/', views.CircuitoCreateView.as_view(), name='circuito_crear'),
    path('admin/circuitos/<int:pk>/editar/', views.CircuitoUpdateView.as_view(), name='circuito_editar'),
    path('admin/circuitos/<int:pk>/eliminar/', views.CircuitoDeleteView.as_view(), name='circuito_eliminar'),
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
    # Anotarse armando la pareja en el mismo paso (sin esperar que el otro acepte)
    path(
        '<int:torneo_pk>/anotarme-con-pareja/',
        views.InscribirseConCompaneroView.as_view(),
        name='inscribirse_con_companero',
    ),
    path(
        'pareja/<int:pk>/salir/',
        views.SalirDeLaParejaView.as_view(),
        name='salir_de_la_pareja',
    ),
    path(
        '<int:torneo_pk>/cancelar-inscripcion/',
        views.InscripcionDeleteView.as_view(),
        name='cancelar_inscripcion',
    ),
    # Vistas de Admin
    path('admin/listado/', views.AdminTorneoListView.as_view(), name='admin_list'),
    path('admin/crear/', views.AdminTorneoCreateView.as_view(), name='admin_crear'),
    # Dashboard del organizador
    path('admin/dashboard/', views.OrganizadorDashboardView.as_view(), name='dashboard'),
    # Embudo de inscripción (solo lectura; alternativa al shell de Render)
    path('admin/embudo/', views.EmbudoInscripcionView.as_view(), name='embudo'),
    # Formatos personalizados (creador de torneos)
    path('admin/formatos/', views.FormatoPersonalizadoListView.as_view(), name='formatos_list'),
    path('admin/formatos/nuevo/', views.FormatoPersonalizadoCreateView.as_view(), name='formato_crear'),
    path('admin/formatos/<int:pk>/editar/', views.FormatoPersonalizadoUpdateView.as_view(), name='formato_editar'),
    path('admin/formatos/<int:pk>/eliminar/', views.FormatoPersonalizadoDeleteView.as_view(), name='formato_eliminar'),
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
        'admin/<int:pk>/inscriptos.csv',
        views.ExportarInscriptosView.as_view(),
        name='exportar_inscriptos',
    ),
    path('admin/<int:pk>/cobros/', views.CobrosTorneoView.as_view(), name='cobros'),
    path(
        'inscripcion/<int:pk>/comprobante/',
        views.SubirComprobanteView.as_view(),
        name='subir_comprobante',
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
    # (Se quitó 'admin/crear-torneo-prueba/': era un GET que borraba datos en masa.
    #  El equivalente seguro es `python manage.py crear_torneo_24`.)
    # Redirección de seguridad para el path base /torneos/
    path('', lambda r: redirect('torneos:abierto_list'), name='base_redirect'),
]

from django.shortcuts import redirect

