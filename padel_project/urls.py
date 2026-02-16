from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import TemplateView
from .sitemaps import StaticViewSitemap, TorneoSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'torneos': TorneoSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    # URLs de Core (Home)
    path('', include('core.urls')),
    # URLs de Accounts (Login, Logout, Registro, Perfil)
    path('accounts/', include('accounts.urls')),
    # URLs de Equipos
    path('equipos/', include('equipos.urls')),
    # URLs de Torneos
    path('torneos/', include('torneos.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
