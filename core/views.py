from django.db.models import Count
from django.shortcuts import render
from torneos.models import Torneo


def home(request):
    """
    Vista principal (Home). Muestra los torneos abiertos y en juego.
    """
    # CORRECCIÓN: Usamos las constantes del modelo (AB, EJ) en lugar de strings crudos
    # Cada tarjeta del home usa organizacion.logo, division.nombre y el conteo de
    # inscriptos: sin select_related/annotate eran 4 queries extra POR torneo.
    base = (
        Torneo.objects
        .select_related('organizacion', 'division')
        .annotate(n_inscriptos=Count('inscripciones'))
        .order_by('fecha_inicio')
    )
    torneos_abiertos = base.filter(estado=Torneo.Estado.ABIERTO)
    torneos_en_juego = base.filter(estado=Torneo.Estado.EN_JUEGO)

    # Importar Organizacion
    from accounts.models import Organizacion
    organizadores = Organizacion.objects.all()

    # Prueba social (TP-04): contadores reales cacheados 1h + testimonios.
    from django.core.cache import cache
    from .models import Testimonio
    stats_home = cache.get('home_stats')
    if stats_home is None:
        from accounts.models import CustomUser
        from torneos.models import Partido, PartidoGrupo
        stats_home = {
            'torneos_jugados': Torneo.objects.filter(estado=Torneo.Estado.FINALIZADO).count(),
            'jugadores': CustomUser.objects.filter(tipo_usuario='PLAYER', is_dummy=False).count(),
            'partidos_jugados': (
                Partido.objects.filter(ganador__isnull=False).count()
                + PartidoGrupo.objects.filter(ganador__isnull=False).count()
            ),
        }
        cache.set('home_stats', stats_home, 3600)

    context = {
        'torneos_abiertos': torneos_abiertos,
        'torneos_en_juego': torneos_en_juego,
        'organizadores': organizadores,
        'stats_home': stats_home,
        'testimonios': Testimonio.objects.filter(activo=True),
    }

    if request.user.is_authenticated and hasattr(request.user, 'equipo') and request.user.equipo:
        from torneos.models import Inscripcion
        inscripciones = Inscripcion.objects.filter(equipo=request.user.equipo)
        context['torneos_inscritos_ids'] = set(inscripciones.values_list('torneo_id', flat=True))
    return render(request, 'core/home.html', context)


from django.views.generic import TemplateView
from django.db.models import Q
from accounts.models import CustomUser
from equipos.models import Equipo


class ParaOrganizadoresView(TemplateView):
    """Landing de captación de organizadores (TP-05)."""
    template_name = "core/para_organizadores.html"


class InstalarAppView(TemplateView):
    """Tutorial para instalar la web app (PWA) en Android / iPhone."""
    template_name = "core/instalar.html"

    def get_context_data(self, **kwargs):
        from django.conf import settings
        context = super().get_context_data(**kwargs)
        context['vapid_public_key'] = settings.VAPID_PUBLIC_KEY
        return context


class GlobalSearchView(TemplateView):
    template_name = "core/search_results.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context['query'] = query

        if query:
            from .utils import normalize_query, extract_dates, get_smart_filter, is_postgres
            import operator
            from functools import reduce
            
            # 1. Detectar fechas (Smart Search)
            detected_dates = extract_dates(query)
            
            # 2. Normalizar palabras clave
            keywords = query.split()
            use_unaccent = is_postgres()
            
            if keywords:
                # --- BUSCAR JUGADORES ---
                player_q_list = [
                    get_smart_filter('nombre', kw, use_unaccent) | 
                    get_smart_filter('apellido', kw, use_unaccent) | 
                    get_smart_filter('email', kw, use_unaccent)
                    for kw in keywords
                ]
                player_q = reduce(operator.and_, player_q_list)
                
                context['jugadores'] = CustomUser.objects.filter(
                    player_q,
                    tipo_usuario='PLAYER'
                ).distinct()[:10]

                # --- BUSCAR TORNEOS (Smart: Nombre OR Fecha OR División) ---
                torneo_filters = []
                
                # Búsqueda por palabras en el nombre
                torneo_name_q_list = [get_smart_filter('nombre', kw, use_unaccent) for kw in keywords]
                torneo_filters.append(reduce(operator.and_, torneo_name_q_list))
                
                # Búsqueda por división
                div_q_list = [get_smart_filter('division__nombre', kw, use_unaccent) for kw in keywords]
                torneo_filters.append(reduce(operator.and_, div_q_list))

                # Búsqueda por fechas detectadas
                if detected_dates:
                    for d in detected_dates:
                        torneo_filters.append(Q(fecha_inicio=d))
                
                # Combinar filtros de torneos con OR
                torneo_q = reduce(operator.or_, torneo_filters)
                
                context['torneos'] = Torneo.objects.filter(
                    torneo_q
                ).select_related('division', 'organizacion').order_by('-fecha_inicio').distinct()[:15]

                # --- BUSCAR EQUIPOS (Nombre) ---
                equipo_q_list = [get_smart_filter('nombre', kw, use_unaccent) for kw in keywords]
                equipo_q = reduce(operator.and_, equipo_q_list)
                context['equipos'] = Equipo.objects.filter(
                    equipo_q
                ).select_related('jugador1', 'jugador2', 'division')[:10]

        return context

# Acá vivía `trigger_migration`: un GET sin CSRF, montado en la RAÍZ del sitio,
# que corría `migrar_rankings_historicos` de forma sincrónica adentro del
# request. Ese comando recalcula las 8 divisiones escaneando todos los partidos
# de todos los torneos, así que el pedido colgaba hasta el timeout del worker; y
# además parchea el caché A NIVEL PROCESO mientras corre, con lo cual los otros
# threads de ese worker atendían con el caché muerto. Siendo GET, un refresh o
# un prefetch del navegador lo volvía a disparar.
#
# La vía segura es la que ya indica `build.sh`: correrlo a mano desde el shell de
# Render con `python manage.py migrar_rankings_historicos`. Mismo criterio con el
# que se quitó `admin/crear-torneo-prueba/`.
