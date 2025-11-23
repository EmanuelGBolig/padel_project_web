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
