import logging
import time
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def notificar_nuevo_torneo(torneo):
    """
    Envía un email a todos los jugadores elegibles cuando se crea un nuevo torneo.
    Elegibilidad:
    - tipo_usuario == PLAYER, is_active=True, is_dummy=False
    - División dentro del rango ±1 del torneo (o cualquier división si el torneo es libre)
    - Género compatible con la categoría del torneo
    """
    from django.core.mail import send_mail, get_connection
    from django.db import models
    from accounts.models import CustomUser
    from torneos.models import Inscripcion

    # 1. Obtener equipos ya inscritos en este torneo
    equipos_inscritos_ids = Inscripcion.objects.filter(torneo=torneo).values_list('equipo_id', flat=True)

    # Usar Brevo para notificaciones de torneos (cupo de 300)
    connection = get_connection('accounts.brevo_backend.BrevoBackend')

    # 2. Filtrar jugadores base
    jugadores = CustomUser.objects.filter(
        tipo_usuario=CustomUser.TipoUsuario.PLAYER,
        is_active=True,
        is_dummy=False,
    ).exclude(email='')

    # 3. Excluir jugadores que ya están inscritos (ya sea como jugador1 o jugador2)
    jugadores = jugadores.exclude(
        models.Q(equipos_como_jugador1__id__in=equipos_inscritos_ids) |
        models.Q(equipos_como_jugador2__id__in=equipos_inscritos_ids)
    )

    logger.info(f"[emails] Torneo '{torneo.nombre}': {jugadores.count()} jugadores PLAYER elegibles (excluyendo ya inscritos).")

    # --- Filtro por género / categoría ---
    if torneo.categoria == 'M':
        jugadores = jugadores.filter(genero='MASCULINO')
    elif torneo.categoria == 'F':
        jugadores = jugadores.filter(genero='FEMENINO')

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
        return 0, 0

    # Materializar el queryset para contar sin releer la DB
    lista_jugadores = list(jugadores)
    total_elegibles = len(lista_jugadores)

    # Notificación push a los mismos elegibles (TP-11; no-op si VAPID no está configurado)
    try:
        from accounts.push import send_push_to_users
        send_push_to_users(
            lista_jugadores,
            title="🎾 Nuevo torneo disponible",
            body=f"{torneo.nombre} — ya podés inscribirte con tu pareja.",
            url=f"/torneos/{torneo.pk}/",
            tag=f"torneo-{torneo.pk}",
        )
    except Exception as e:
        logger.warning(f"[push] No se pudo encolar la notificación del torneo: {e}")

    # --- Armar y enviar los mensajes ---
    site_url = getattr(settings, 'SITE_URL', 'https://todopadel.club')
    torneo_url = f"{site_url}/torneos/{torneo.pk}/"
    from_email = settings.DEFAULT_FROM_EMAIL
    asunto = f"🎾 Nuevo torneo disponible: {torneo.nombre}"

    def enviar_emails_en_segundo_plano():
        enviados = 0
        for jugador in lista_jugadores:
            contexto = {
                'jugador': jugador,
                'torneo': torneo,
                'torneo_url': torneo_url,
            }
            html_message = render_to_string('torneos/emails/nuevo_torneo.html', contexto)
            plain_message = strip_tags(html_message)

            try:
                send_mail(
                    subject=asunto,
                    message=plain_message,
                    from_email=from_email,
                    recipient_list=[jugador.email],
                    html_message=html_message,
                    fail_silently=False,
                    connection=connection,  # Usar la conexión de Brevo
                )
                enviados += 1
                logger.info(f"[emails] Email enviado a {jugador.email}.")
                time.sleep(0.6)  # Resend permite max 2 req/seg
            except Exception as e:
                logger.error(f"[emails] Error enviando a {jugador.email}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"[emails] Resend response: {e.response.text}")
                time.sleep(0.6)  # También esperar en error para no acumular

        logger.info(f"[emails] Torneo '{torneo.nombre}': {enviados}/{total_elegibles} emails enviados en segundo plano.")

    import threading
    threading.Thread(target=enviar_emails_en_segundo_plano).start()

    logger.info(f"[emails] Torneo '{torneo.nombre}': enviando {total_elegibles} emails en segundo plano.")
    return 0, total_elegibles

def notificar_nueva_inscripcion(inscripcion):
    """
    Envía un email a los organizadores del torneo cuando una nueva pareja se inscribe.
    """
    from django.core.mail import send_mail, get_connection
    from django.conf import settings
    
    torneo = inscripcion.torneo
    equipo = inscripcion.equipo
    
    if not torneo.organizacion:
        return
        
    receptor = torneo.organizacion.receptor_notificaciones
    emails_organizadores = []
    destinatario_push = None

    if receptor and receptor.email:
        emails_organizadores.append(receptor.email)
        destinatario_push = receptor
    else:
        # Fallback al primer organizador si no hay uno explícitamente seleccionado
        organizador_fallback = torneo.organizacion.miembros.filter(tipo_usuario='ORGANIZER').exclude(email='').first()
        if organizador_fallback:
            emails_organizadores.append(organizador_fallback.email)
            destinatario_push = organizador_fallback

    # Push al organizador (TP-11; no-op si VAPID no está configurado)
    if destinatario_push:
        try:
            from accounts.push import send_push_to_user
            send_push_to_user(
                destinatario_push,
                title="📝 Nueva inscripción",
                body=f"{equipo.nombre} se anotó en {torneo.nombre}.",
                url=f"/torneos/admin/{torneo.pk}/gestionar/",
                tag=f"inscripcion-{inscripcion.pk}",
            )
        except Exception:
            pass

    if not emails_organizadores:
        return
    
    site_url = getattr(settings, 'SITE_URL', 'https://todopadel.club')
    torneo_url = f"{site_url}/torneos/admin/{torneo.pk}/gestionar/"
    from_email = settings.DEFAULT_FROM_EMAIL
    asunto = f"🎾 Nueva inscripción: {torneo.nombre}"
    
    contexto = {
        'torneo': torneo,
        'equipo': equipo,
        'torneo_url': torneo_url,
    }
    
    html_message = render_to_string('torneos/emails/nueva_inscripcion.html', contexto)
    plain_message = strip_tags(html_message)
    
    # Usar Brevo para notificaciones
    connection = get_connection('accounts.brevo_backend.BrevoBackend')
    
    def enviar():
        try:
            send_mail(
                subject=asunto,
                message=plain_message,
                from_email=from_email,
                recipient_list=emails_organizadores,
                html_message=html_message,
                fail_silently=False,
                connection=connection,
            )
            logger.info(f"[emails] Nueva inscripción enviada a {len(emails_organizadores)} organizadores.")
        except Exception as e:
            logger.error(f"[emails] Error enviando inscripción a organizadores: {e}")
            
    import threading
    threading.Thread(target=enviar).start()
