from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from torneos.models import Torneo

class StaticViewSitemap(Sitemap):
    # `priority` y `changefreq` son métodos más abajo, no atributos: Django los
    # llama con el item si son invocables. Por eso acá no hay valores fijos.

    # La landing comercial es la página por la que queremos que nos encuentre un
    # organizador de club buscando cómo armar un torneo, así que va con la
    # prioridad más alta de las estáticas. Y no cambia a diario como los
    # listados: es contenido fijo de venta, y decirle a Google que cambia todos
    # los días es pedirle que la recorra al vacío.
    #
    # El resto queda EXACTAMENTE con los valores de antes (0.5 / daily), aunque
    # para `accounts:login` tampoco tengan mucho sentido: cambiarlos es otro
    # tema y no se mezcla acá.
    ESPECIALES = {
        'core:para_organizadores': {'priority': 0.9, 'changefreq': 'monthly'},
    }

    def items(self):
        # `accounts:login` y `accounts:registro` NO van: `robots.txt` declara
        # `Disallow: /accounts/`, así que listarlos era pedirle a Google que
        # indexara URLs a las que le prohibimos entrar. Y además un login no es
        # una página de entrada desde una búsqueda: el que llega de Google
        # quiere ver torneos, no un formulario.
        #
        # `accounts:rankings_jugadores` SÍ va, aunque también cae bajo ese
        # `Disallow`: es contenido público y de los que mejor rankean ("ranking
        # de pádel <ciudad>"). Esa contradicción se resolvió del otro lado, con
        # un `Allow` más específico en `templates/robots.txt`.
        return [
            'core:home',
            'core:para_organizadores',
            'accounts:rankings_jugadores',
            'torneos:circuito_list',
            'torneos:abierto_list',
            'torneos:en_juego_list',
            'torneos:finalizado_list',
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.ESPECIALES.get(item, {}).get('priority', 0.5)

    def changefreq(self, item):
        return self.ESPECIALES.get(item, {}).get('changefreq', 'daily')

class TorneoSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        # Ordenado a propósito: `Torneo` no tiene `Meta.ordering`, y un sitemap
        # pagina de a 50.000 URLs. Con un queryset sin orden, cada página se
        # arma con un `LIMIT/OFFSET` sobre un orden que la base no garantiza, y
        # entre página y página un torneo puede repetirse o faltar. Hoy no pasa
        # porque hay pocos, pero Django lo avisa con `UnorderedObjectListWarning`
        # en CADA pedido al sitemap.
        return Torneo.objects.order_by('-fecha_inicio', 'pk')

    def lastmod(self, obj):
        # Asumiendo que Torneo tiene un campo de fecha de actualización o creación
        # Si no, devolver None o la fecha de inicio
        return obj.fecha_inicio


class CitySitemap(Sitemap):
    """Páginas por ciudad (SEO local, TP-14)."""
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return list(
            Torneo.objects.exclude(ciudad='')
            .values_list('ciudad', flat=True)
            .distinct()
        )

    def location(self, item):
        return reverse('torneos:ciudad', args=[item])
