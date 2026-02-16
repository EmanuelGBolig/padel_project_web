from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from torneos.models import Torneo

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['core:home', 'accounts:login', 'accounts:registro']

    def location(self, item):
        return reverse(item)

class TorneoSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Torneo.objects.all()

    def lastmod(self, obj):
        # Asumiendo que Torneo tiene un campo de fecha de actualización o creación
        # Si no, devolver None o la fecha de inicio
        return obj.fecha_inicio
