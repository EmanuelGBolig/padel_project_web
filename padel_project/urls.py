from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import TemplateView, RedirectView
from .sitemaps import StaticViewSitemap, TorneoSitemap, CitySitemap

sitemaps = {
    'static': StaticViewSitemap,
    'torneos': TorneoSitemap,
    'ciudades': CitySitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('googleed7ca9e7f31e28a7.html', TemplateView.as_view(template_name="googleed7ca9e7f31e28a7.html", content_type="text/html")),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'img/favicon.ico', permanent=True)),
    # PWA: servidos en la raíz para que el scope del service worker sea "/"
    path('sw.js', TemplateView.as_view(template_name="pwa/sw.js", content_type="application/javascript")),
    path('manifest.webmanifest', TemplateView.as_view(template_name="pwa/manifest.webmanifest", content_type="application/manifest+json")),
    # URLs de Core (Home)
    path('', include('core.urls')),
    # URLs de Accounts (Login, Logout, Registro, Perfil)
    path('accounts/', include('accounts.urls')),
    # URLs de Equipos
    path('equipos/', include('equipos.urls')),
    # URLs de Torneos
    path('torneos/', include('torneos.urls')),
    # URLs de Google OAuth2
    path('social-auth/', include('social_django.urls', namespace='social')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# iOS pide estos dos en la RAÍZ del dominio cuando no encuentra el <link> del
# HTML (por ejemplo al agregar a la pantalla de inicio desde un marcador viejo).
# Tienen que llevar al icono opaco de 180x180, no al de 192 que era transparente
# en las esquinas: iOS rellena de blanco lo transparente y quedaba el halo.
urlpatterns += [
    path('apple-touch-icon.png', RedirectView.as_view(
        url=settings.STATIC_URL + 'img/apple-touch-icon.png', permanent=True)),
    path('apple-touch-icon-precomposed.png', RedirectView.as_view(
        url=settings.STATIC_URL + 'img/apple-touch-icon.png', permanent=True)),
]
