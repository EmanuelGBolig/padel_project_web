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
    # Acá estaba 'trigger-migration/': un GET sin CSRF, en la raíz del sitio, que
    # corría un recálculo global de rankings adentro del request. El equivalente
    # seguro es `python manage.py migrar_rankings_historicos` (ver `build.sh`).
]
