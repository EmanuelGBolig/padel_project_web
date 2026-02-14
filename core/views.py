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

    context = {
        'torneos_abiertos': torneos_abiertos,
        'torneos_en_juego': torneos_en_juego,
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
            # Buscar Jugadores (nombre, apellido, email)
            context['jugadores'] = CustomUser.objects.filter(
                Q(nombre__icontains=query) | 
                Q(apellido__icontains=query) | 
                Q(email__icontains=query),
                tipo_usuario='PLAYER'
            ).distinct()[:10]  # Limitar a 10 resultados

            # Buscar Torneos (nombre)
            context['torneos'] = Torneo.objects.filter(
                nombre__icontains=query
            ).order_by('-fecha_inicio')[:10]

            # Buscar Equipos (nombre)
            context['equipos'] = Equipo.objects.filter(
                nombre__icontains=query
            )[:10]

        return context
