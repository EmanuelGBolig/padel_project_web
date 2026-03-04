import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notificar_nuevo_torneo(torneo):
    """
    Envía un email a todos los jugadores elegibles cuando se crea un nuevo torneo.
    Elegibilidad:
    - tipo_usuario == PLAYER, is_active=True, is_dummy=False
    - División dentro del rango ±1 del torneo (o cualquier división si el torneo es libre)
    - Género compatible con la categoría del torneo
    """
    from accounts.models import CustomUser

    jugadores = CustomUser.objects.filter(
        tipo_usuario=CustomUser.TipoUsuario.PLAYER,
        is_active=True,
        is_dummy=False,
    ).exclude(email='')

    logger.info(f"[emails] Torneo '{torneo.nombre}': {jugadores.count()} jugadores PLAYER activos antes de filtros.")

    # --- Filtro por género / categoría ---
    if torneo.categoria == 'M':
        jugadores = jugadores.filter(genero='MASCULINO')
    elif torneo.categoria == 'F':
        jugadores = jugadores.filter(genero='FEMENINO')
    # Mixto ('X') → no filtramos por género

    logger.info(f"[emails] Tras filtro género ({torneo.get_categoria_display()}): {jugadores.count()} jugadores.")

    # --- Filtro por división ---
    if torneo.division is not None:
        orden_torneo = torneo.division.orden
        jugadores = jugadores.filter(
            division__orden__gte=orden_torneo - 1,
            division__orden__lte=orden_torneo + 1,
        )

    logger.info(f"[emails] Tras filtro división ({torneo.division}): {jugadores.count()} jugadores elegibles.")

    if not jugadores.exists():
        logger.info(f"[emails] Torneo '{torneo.nombre}': no hay jugadores elegibles, no se envían emails.")
        return

    # --- Armar y enviar los mensajes ---
    site_url = getattr(settings, 'SITE_URL', 'https://todopadel.club')
    torneo_url = f"{site_url}/torneos/{torneo.pk}/"
    from_email = settings.DEFAULT_FROM_EMAIL if not settings.DEBUG else 'noreply@todopadel.club'
    asunto = f"🎾 Nuevo torneo disponible: {torneo.nombre}"

    enviados = 0
    for jugador in jugadores:
        contexto = {
            'jugador': jugador,
            'torneo': torneo,
            'torneo_url': torneo_url,
        }
        cuerpo_texto = (
            f"Hola {jugador.full_name},\n\n"
            f"Se abrió la inscripción para el torneo: {torneo.nombre}\n"
            f"División: {torneo.division or 'Libre'}\n"
            f"Categoría: {torneo.get_categoria_display()}\n"
            f"Fecha: {torneo.fecha_inicio.strftime('%d/%m/%Y')}\n\n"
            f"Inscribite acá: {torneo_url}\n\n"
            f"— El equipo de TodoPadel"
        )
        cuerpo_html = render_to_string('torneos/emails/nuevo_torneo.html', contexto)

        msg = EmailMultiAlternatives(
            subject=asunto,
            body=cuerpo_texto,
            from_email=from_email,
            to=[jugador.email],
        )
        msg.attach_alternative(cuerpo_html, 'text/html')
        msg.send(fail_silently=False)
        enviados += 1
        logger.info(f"[emails] Email enviado a {jugador.email}.")

    logger.info(f"[emails] Torneo '{torneo.nombre}': {enviados} emails enviados correctamente.")
