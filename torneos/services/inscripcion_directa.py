"""Inscribirse a un torneo armando la pareja en el mismo paso.

Hasta acá el jugador tenía que: crear cuenta -> invitar al compañero -> esperar
que acepte -> recién ahí inscribirse. En los hechos el 74% de las parejas las
terminaba creando el organizador a mano para saltear ese ida y vuelta.

Acá el jugador hace lo mismo que ya podía hacer el organizador: deja la pareja
y la inscripción hechas en un solo paso. La confirmación del compañero pasa a ser
un aviso (puede rechazar y se deshace), no una tranca previa.
"""
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction

from equipos.models import Equipo, Invitation

from ..models import Inscripcion, Torneo


class InscripcionError(Exception):
    """Algo impide inscribirse. El mensaje va derecho al usuario."""


def _normalizar_telefono(crudo):
    return ''.join(c for c in (crudo or '') if c.isdigit())


def buscar_por_telefono(telefono):
    """Busca un jugador por teléfono, ignorando formato.

    Evita duplicar a alguien que ya está en la app con otro formato de número.
    Usa el mismo criterio que el alta sin cuenta: 10 dígitos, igualdad exacta y
    match único (ver `alta_sin_cuenta.buscar_jugador` para el porqué).
    """
    from .alta_sin_cuenta import _cola_telefono

    cola = _cola_telefono(telefono)
    if not cola:
        return None

    User = get_user_model()
    vivos = User.objects.filter(merged_into__isnull=True)
    candidatos = [
        pk for pk, numero in vivos.exclude(numero_telefono='')
                                  .exclude(numero_telefono__isnull=True)
                                  .values_list('id', 'numero_telefono')
        if _cola_telefono(numero) == cola
    ]
    if len(candidatos) != 1:
        return None
    return vivos.filter(pk=candidatos[0]).first()


def crear_companero_sin_cuenta(nombre, apellido, telefono, division, genero=''):
    """Crea un jugador que todavía no está en la app.

    Queda como dummy (no puede loguear) hasta que reclame la cuenta con el link
    que se le manda por WhatsApp.
    """
    User = get_user_model()
    return User.objects.create(
        nombre=(nombre or '').strip()[:150],
        apellido=(apellido or '').strip()[:150],
        numero_telefono=(telefono or '').strip()[:20],
        division=division,
        genero=genero or 'OTRO',
        email=f"pendiente_{uuid.uuid4().hex[:10]}@padel.local",
        tipo_usuario='PLAYER',
        is_dummy=True,
        is_active=False,
    )


def validar(usuario, torneo, companero):
    """Corre todas las reglas. Lanza InscripcionError con el motivo."""
    from ..views import es_division_permitida  # import tardío: evita el ciclo

    if not usuario.division:
        raise InscripcionError(
            "Antes de anotarte necesitás elegir tu división en el perfil."
        )
    if companero and companero.pk == usuario.pk:
        raise InscripcionError("No podés anotarte con vos mismo.")

    if torneo.estado != Torneo.Estado.ABIERTO:
        raise InscripcionError("La inscripción de este torneo está cerrada.")
    if torneo.cupos_disponibles <= 0:
        raise InscripcionError(
            f"«{torneo.nombre}» ya cubrió sus {torneo.cupos_totales} cupos."
        )

    if usuario.equipo:
        raise InscripcionError(
            f"Ya tenés pareja armada ({usuario.equipo.nombre}). "
            "Si querés cambiarla, primero disolvela."
        )
    if companero and companero.equipo:
        raise InscripcionError(
            f"{companero.full_name} ya forma parte de otra pareja."
        )


def inscribir_con_companero(usuario, torneo, companero, categoria=None):
    """Crea la pareja y la inscripción en una sola transacción.

    Devuelve (equipo, inscripcion, invitacion). `invitacion` puede ser None si el
    compañero todavía no tiene cuenta (a ese se le avisa por WhatsApp).
    """
    from ..views import es_division_permitida

    validar(usuario, torneo, companero)

    # La división de la pareja es la del jugador de división más alta (menor orden),
    # igual que hace Equipo.save().
    with transaction.atomic():
        equipo = Equipo(
            jugador1=usuario,
            jugador2=companero,
            division=usuario.division,
        )
        if categoria:
            equipo.categoria = categoria
        equipo.save()   # asigna nombre, división y ordena los FKs

        if not es_division_permitida(equipo, torneo):
            raise InscripcionError(
                f"La pareja no puede jugar un torneo de "
                f"{torneo.division.nombre if torneo.division else 'esta categoría'} "
                "por la diferencia de divisiones entre ustedes."
            )

        # Re-chequeo del cupo bajo lock: entre la validación y acá pudo entrar otro.
        bloqueado = Torneo.objects.select_for_update().get(pk=torneo.pk)
        if bloqueado.inscripciones.count() >= bloqueado.cupos_totales:
            raise InscripcionError(
                "Justo se completaron los cupos. Escribile al organizador."
            )

        inscripcion = Inscripcion.objects.create(torneo=torneo, equipo=equipo)

        # Si el compañero tiene cuenta, le dejamos una invitación PENDIENTE.
        # Ojo: acá NO bloquea nada — la pareja y la inscripción ya están hechas.
        # Sirve para que se entere y para que pueda deshacerlo si fue un error.
        invitacion = None
        if not companero.is_dummy:
            Invitation.objects.filter(
                inviter=usuario, invited=companero,
                status=Invitation.Status.PENDING,
            ).delete()
            invitacion = Invitation.objects.create(
                inviter=usuario,
                invited=companero,
                status=Invitation.Status.PENDING,
            )

    return equipo, inscripcion, invitacion


def deshacer(equipo, torneo=None):
    """Deshace la pareja (y su inscripción) cuando el compañero dice que no.

    No borra el Equipo: lo desactiva, para no dejar huecos si llegó a jugar algo.
    """
    with transaction.atomic():
        qs = Inscripcion.objects.filter(equipo=equipo)
        if torneo:
            qs = qs.filter(torneo=torneo)
        qs.delete()

        equipo.esta_activo = False
        equipo.save(update_fields=['esta_activo'])
