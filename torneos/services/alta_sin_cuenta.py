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

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from equipos.models import Equipo

from ..models import Inscripcion, Torneo


# La lógica de identificar personas (normalizar teléfonos, generar claves,
# enganchar a alguien ya cargado) vive en `accounts.identidad`: no es de
# torneos, y la necesitan también el alta de jugadores del organizador y la
# creación de parejas. Se re-exporta acá porque varios módulos y tests ya la
# importaban desde este archivo.
from accounts.identidad import (  # noqa: F401
    AltaError,
    DIGITOS_TELEFONO,
    _cola_telefono,
    _sin_acentos,
    _solo_digitos,
    buscar_jugador,
    generar_password,
)


# Vocales y sus variantes acentuadas, para buscar sin depender de la tilde.
_EQUIVALENTES = {
    'a': 'aáàäâ', 'e': 'eéèëê', 'i': 'iíìïî',
    'o': 'oóòöô', 'u': 'uúùüû', 'n': 'nñ', 'c': 'cç',
}


def _parece_telefono(texto):
    """True si la consulta es un numero y no un nombre.

    Se mira que NO tenga letras, en vez de que tenga digitos: "Sim1" tiene un
    digito y es claramente un apellido, y con el criterio anterior se iba por la
    rama de telefono y no encontraba a nadie.
    """
    return bool(texto) and not any(c.isalpha() for c in texto)


def _patron_sin_acentos(palabra):
    """Regex que matchea la palabra ignorando tildes y enies.

    Los apellidos argentinos estan llenos de tildes (Gomez/Gómez,
    Martin/Martín, Nunez/Núñez) y nadie las escribe al buscar en el celular.
    `icontains` es literal, asi que "Gomez" no encontraba a "Gómez" y el
    buscador parecia roto.

    Se resuelve del lado de la consulta y no de la base: `unaccent` de Postgres
    obligaria a una extension y a una migracion, y en desarrollo la base es
    SQLite. `iregex` anda igual en las dos.
    """
    # Se le sacan las tildes tambien a lo que escribio el usuario: si escribe
    # "Gómez" tiene que encontrar igual a los "Gomez" cargados sin tilde.
    # La enie se traduce aparte porque NFKD la parte en "n" + tilde.
    palabra = _sin_acentos(palabra.lower()).replace('̃', '')
    partes = []
    for caracter in palabra:
        equivalentes = _EQUIVALENTES.get(caracter)
        if equivalentes:
            partes.append(f'[{equivalentes}]')
        elif caracter.isalnum():
            partes.append(re.escape(caracter))
        # Lo demas (comillas, guiones sueltos) se ignora: no aporta a la busqueda
        # y podria romper la expresion.
    return ''.join(partes)


def buscar_companeros(consulta, limite=8):
    """Busca jugadores para el selector de "mi compañero ya tiene cuenta".

    Lo consume un endpoint PUBLICO (el alta sin cuenta no pide login a
    proposito), asi que esta escrito para no convertirse en un directorio
    scrapeable de la base de usuarios:

    - El nombre se busca por partes, pero exige al menos 3 caracteres.
    - El email y el telefono se buscan **exactos**. Con `icontains` alcanzaba
      con probar "@gmail" para listar medio padron; asi hay que saber el dato.
    - Nunca se devuelve el email ni el telefono de nadie: solo el nombre y la
      division, que es lo unico que hace falta para reconocer a la persona.

    Devuelve una lista de dicts listos para serializar.
    """
    User = get_user_model()
    consulta = (consulta or '').strip()
    if len(consulta) < 3:
        return []

    vivos = User.objects.filter(
        merged_into__isnull=True, tipo_usuario='PLAYER',
    ).select_related('division')

    # Email exacto: quien lo sabe, ya conoce a la persona.
    if '@' in consulta:
        encontrados = vivos.filter(email__iexact=consulta)[:limite]
    elif _parece_telefono(consulta):
        cola = _cola_telefono(consulta)
        if not cola:
            # Son numeros pero no alcanzan para un telefono. No se busca por
            # nombre (no tendria sentido) ni se devuelve media base.
            return []
        # Telefono completo: se compara normalizado, igual que el enganche.
        ids = [
            pk for pk, numero in vivos.exclude(numero_telefono='')
                                      .exclude(numero_telefono__isnull=True)
                                      .values_list('id', 'numero_telefono')
            if _cola_telefono(numero) == cola
        ]
        encontrados = vivos.filter(pk__in=ids)[:limite]
    else:
        filtro = Q()
        for palabra in consulta.split()[:3]:
            patron = _patron_sin_acentos(palabra)
            filtro &= (Q(nombre__iregex=patron) | Q(apellido__iregex=patron))
        encontrados = vivos.filter(filtro).order_by(
            'nombre', 'apellido')[:limite]

    return [
        {
            'id': u.pk,
            'nombre': u.full_name,
            # Sin email ni telefono: con la division alcanza para distinguir
            # entre dos homonimos, y no filtra datos de contacto.
            'detalle': u.division.nombre if u.division else 'Sin division',
        }
        for u in encontrados
    ]


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

    # Si eligio a su companero del buscador, la cuenta ya esta resuelta: no hay
    # nada que crear ni que adivinar, y no se le toca la contrasena.
    elegido = datos.get('companero_usuario')
    if elegido is not None:
        companero, pass_comp, comp_existia = elegido, None, True
    else:
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
