"""Anotarse a un torneo sin tener cuenta.

El jugador carga sus datos y los de su compañero/a, y el sistema:

1. Busca si esa persona YA está en la base — incluyendo los jugadores que el
   organizador cargó a mano ("dummies"). Si la encuentra, reusa esa cuenta con
   todo su historial en vez de crear una duplicada.
2. Si no está, le crea la cuenta con una contraseña automática.
3. Arma la pareja y la inscripción.
4. Deja listo el mensaje de WhatsApp para avisarle al compañero.

Sobre la contraseña: es `nombre` + 4 dígitos al azar. Se dicta por WhatsApp, así
que tiene que ser fácil de tipear, pero `nombre123` sería adivinable por
cualquiera que sepa quién juega — y esa persona vería el teléfono y el historial
del otro. Los 4 dígitos lo evitan sin complicar el mensaje. En todos los casos se
marca `debe_cambiar_password`: la app le pide cambiarla al entrar.
"""
import re
import secrets
import unicodedata

from django.contrib.auth import get_user_model
from django.db import transaction

from equipos.models import Equipo

from ..models import Inscripcion, Torneo


class AltaError(Exception):
    """Algo impide completar el alta. El mensaje va derecho al usuario."""


def _solo_digitos(texto):
    return re.sub(r'\D', '', texto or '')


def _sin_acentos(texto):
    nfkd = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def generar_password(nombre):
    """`nombre` + 4 dígitos al azar. Fácil de dictar, no adivinable."""
    base = _sin_acentos(nombre).strip().lower()
    base = re.sub(r'[^a-z]', '', base)[:12] or 'padel'
    return f"{base}{secrets.randbelow(9000) + 1000}"


def buscar_jugador(email=None, telefono=None):
    """Busca una persona ya cargada, por email o por teléfono.

    Mira también los jugadores que creó el organizador: si el tipo ya está en la
    base como dummy, queremos ENGANCHAR esa cuenta (con su historial de partidos)
    y no crear una nueva en paralelo.
    """
    User = get_user_model()

    if email:
        u = User.objects.filter(email__iexact=email.strip()).first()
        if u:
            return u

    digitos = _solo_digitos(telefono)
    if len(digitos) >= 8:
        cola = digitos[-8:]     # cubre +54 9 / 0 / 15 y separadores
        for u in User.objects.exclude(numero_telefono='').exclude(numero_telefono__isnull=True):
            if _solo_digitos(u.numero_telefono).endswith(cola):
                return u
    return None


def obtener_o_crear_jugador(nombre, apellido, email, telefono, division):
    """Devuelve (usuario, password_generada, ya_existia).

    `password_generada` es None si la cuenta ya existía: no tocamos la contraseña
    de nadie.
    """
    User = get_user_model()
    existente = buscar_jugador(email=email, telefono=telefono)

    if existente:
        # Si era un dummy del organizador, lo "ascendemos" a cuenta real
        # conservando su historial: mismo id, mismos partidos, mismo ranking.
        if existente.is_dummy:
            password = generar_password(existente.nombre or nombre)
            existente.is_dummy = False
            existente.is_active = True
            existente.debe_cambiar_password = True
            if email and existente.email.endswith('@padel.local'):
                existente.email = email.strip()
            if telefono and not existente.numero_telefono:
                existente.numero_telefono = telefono.strip()
            if not existente.division_id and division:
                existente.division = division
            existente.set_password(password)
            existente.save()
            return existente, password, True
        return existente, None, True

    if not email:
        raise AltaError("Necesitamos un email para crear la cuenta.")

    password = generar_password(nombre)
    usuario = User.objects.create_user(
        email=email.strip(),
        password=password,
        nombre=(nombre or '').strip()[:150],
        apellido=(apellido or '').strip()[:150],
    )
    usuario.numero_telefono = (telefono or '').strip()[:20]
    usuario.division = division
    usuario.tipo_usuario = 'PLAYER'
    usuario.debe_cambiar_password = True
    usuario.save()
    return usuario, password, False


def mensaje_bienvenida(usuario, password, torneo):
    """Texto del WhatsApp para el compañero/a."""
    if password:
        acceso = (
            f"\n\nYa tenés tu cuenta para ver tus estadísticas y partidos! "
            f"Solo tenés que entrar con:\n"
            f"Mail: {usuario.email}\n"
            f"Contraseña: {password}\n"
            f"(podés cambiarla cuando entres)"
        )
    else:
        acceso = "\n\nEntrá con tu cuenta de siempre para ver tus partidos."

    return (
        f"Hola {usuario.nombre}! Te anoté al torneo {torneo.nombre}."
        f"{acceso}"
    )


@transaction.atomic
def inscribir_sin_cuenta(torneo, datos):
    """Crea (o engancha) las dos cuentas, arma la pareja y la inscripción.

    `datos` viene del form ya validado. Devuelve un dict con lo necesario para la
    pantalla de confirmación.
    """
    from ..views import es_division_permitida

    if torneo.estado != Torneo.Estado.ABIERTO:
        raise AltaError("La inscripción de este torneo está cerrada.")
    if torneo.cupos_disponibles <= 0:
        raise AltaError(f"«{torneo.nombre}» ya cubrió sus {torneo.cupos_totales} cupos.")

    division = datos.get('division') or torneo.division

    yo, pass_yo, yo_existia = obtener_o_crear_jugador(
        datos['nombre'], datos['apellido'], datos['email'], datos['telefono'], division)
    companero, pass_comp, comp_existia = obtener_o_crear_jugador(
        datos['companero_nombre'], datos['companero_apellido'],
        datos.get('companero_email'), datos['companero_telefono'], division)

    if yo.pk == companero.pk:
        raise AltaError("Cargaste los mismos datos para los dos jugadores.")

    for persona in (yo, companero):
        if persona.equipo:
            raise AltaError(
                f"{persona.full_name} ya forma parte de otra pareja en este momento."
            )

    equipo = Equipo(jugador1=yo, jugador2=companero, division=division)
    equipo.save()

    if not es_division_permitida(equipo, torneo):
        raise AltaError(
            "La pareja no puede jugar este torneo por la diferencia de divisiones."
        )

    bloqueado = Torneo.objects.select_for_update().get(pk=torneo.pk)
    if bloqueado.inscripciones.count() >= bloqueado.cupos_totales:
        raise AltaError("Justo se completaron los cupos. Escribile al organizador.")

    inscripcion = Inscripcion.objects.create(torneo=torneo, equipo=equipo)

    return {
        'equipo': equipo,
        'inscripcion': inscripcion,
        'yo': yo,
        'password_yo': pass_yo,
        'yo_existia': yo_existia,
        'companero': companero,
        'password_companero': pass_comp,
        'companero_existia': comp_existia,
        'mensaje_companero': mensaje_bienvenida(companero, pass_comp, torneo),
    }
