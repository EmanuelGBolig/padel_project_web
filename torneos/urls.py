from django.urls import path
from . import views

app_name = 'torneos'

urlpatterns = [
    # Vistas de Jugador
    path(
        'finalizados/', views.TorneoFinalizadoListView.as_view(), name='finalizado_list'
    ),
    path('<int:pk>/', views.TorneoDetailView.as_view(), name='detail'),
    path(
        '<int:torneo_pk>/inscribirse/',
        views.InscripcionCreateView.as_view(),
        name='inscribirse',
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
]
