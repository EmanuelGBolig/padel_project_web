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
            import operator
            from functools import reduce
            
            # Split query into words
            keywords = query.split()
            
            # Buscar Jugadores (nombre, apellido, email) - TODAS las palabras deben coincidir en alguno de los campos
            if keywords:
                # Build an AND query across words: for each word, it must be in nombre OR apellido OR email
                player_q_list = [
                    Q(nombre__icontains=kw) | Q(apellido__icontains=kw) | Q(email__icontains=kw)
                    for kw in keywords
                ]
                player_q = reduce(operator.and_, player_q_list)
                
                context['jugadores'] = CustomUser.objects.filter(
                    player_q,
                    tipo_usuario='PLAYER'
                ).distinct()[:10]  # Limitar a 10 resultados

                # Buscar Torneos (nombre)
                torneo_q_list = [Q(nombre__icontains=kw) for kw in keywords]
                torneo_q = reduce(operator.and_, torneo_q_list)
                context['torneos'] = Torneo.objects.filter(
                    torneo_q
                ).order_by('-fecha_inicio')[:10]

                # Buscar Equipos (nombre)
                equipo_q_list = [Q(nombre__icontains=kw) for kw in keywords]
                equipo_q = reduce(operator.and_, equipo_q_list)
                context['equipos'] = Equipo.objects.filter(
                    equipo_q
                )[:10]

        return context
