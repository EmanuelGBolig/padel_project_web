from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('para-organizadores/', views.ParaOrganizadoresView.as_view(), name='para_organizadores'),
    # Atajo para dictar por telefono o WhatsApp: /clubes -> /para-organizadores/
    path(
        'clubes/',
        RedirectView.as_view(pattern_name='core:para_organizadores', permanent=True),
        name='clubes',
    ),
    path('instalar/', views.InstalarAppView.as_view(), name='instalar'),
    path('search/', views.GlobalSearchView.as_view(), name='search'),
    path('trigger-migration/', views.trigger_migration, name='trigger_migration'),
]
