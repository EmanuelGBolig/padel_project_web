from django.shortcuts import render
from torneos.models import Torneo


def home(request):
    """
    Vista principal (Home). Muestra los torneos abiertos y en juego.
    """
    # CORRECCIÓN: Usamos las constantes del modelo (AB, EJ) en lugar de strings crudos
    torneos_abiertos = Torneo.objects.filter(estado=Torneo.Estado.ABIERTO).order_by(
        'fecha_inicio'
    )

    torneos_en_juego = Torneo.objects.filter(estado=Torneo.Estado.EN_JUEGO).order_by(
        'fecha_inicio'
    )
    
    # Importar Organizacion
    from accounts.models import Organizacion
    organizadores = Organizacion.objects.all()

    context = {
        'torneos_abiertos': torneos_abiertos,
        'torneos_en_juego': torneos_en_juego,
        'organizadores': organizadores,
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

from django.core.management import call_command
from django.http import HttpResponse

def trigger_migration(request):
    if not request.user.is_superuser:
        return HttpResponse("No autorizado (Solo Superusuarios)", status=401)
    
    try:
        call_command('migrar_rankings_historicos')
        return HttpResponse("<h1>¡Migración Completada con Éxito!</h1><p>Todos los puntos han sido recalculados y guardados en la BD de producción.</p><a href='/'>Volver al Inicio</a>")
    except Exception as e:
        return HttpResponse(f"<h1>Error</h1><p>{str(e)}</p>", status=500)
