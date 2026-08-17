"""Identificar personas: normalizar teléfonos, generar claves, buscar duplicados.

Todo esto vivía en `torneos/services/alta_sin_cuenta.py`, pero no es lógica de
torneos: es de cuentas. Y hacía falta también en el alta de jugadores del
organizador (`accounts`) y en la creación de parejas (`equipos`), que no pueden
importar de `torneos` sin invertir la dependencia.

`alta_sin_cuenta` sigue re-exportando estos nombres, así que nada de lo que ya
los usaba cambió.
"""
import re
import secrets
import unicodedata

from django.contrib.auth import get_user_model
from django.db.models import Q


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


# Cuántos dígitos finales tienen que coincidir para dar dos teléfonos por
# iguales. En Argentina el número significativo es característica + abonado = 10
# (223 5937115). Con 8 —como estaba— dos números de ciudades distintas podían
# coincidir, y entonces se anotaba a un tercero y se le mostraban sus datos a
# quien estaba cargando el alta.
DIGITOS_TELEFONO = 10


def _cola_telefono(texto):
    """Número argentino normalizado a característica + abonado (10 dígitos).

    Devuelve None si no se puede llevar a esa forma: preferimos no comparar
    antes que comparar mal. Cubre las formas en que la gente escribe el mismo
    número:

        +54 9 223 593-7115   ->  2235937115
        0223 15 593-7115     ->  2235937115
        223 5937115          ->  2235937115
    """
    d = _solo_digitos(texto)
    if d.startswith('54'):          # país
        d = d[2:]
        if d.startswith('9'):       # marca de celular que va después del país
            d = d[1:]
    d = d.lstrip('0')               # 0 de larga distancia
    # Forma vieja: característica + 15 + abonado. Si sacando el "15" queda un
    # número de 10 dígitos, era eso.
    if len(d) == DIGITOS_TELEFONO + 2:
        for corte in (2, 3, 4):
            if d[corte:corte + 2] == '15':
                d = d[:corte] + d[corte + 2:]
                break
    if len(d) < DIGITOS_TELEFONO:
        return None
    return d[-DIGITOS_TELEFONO:]


def buscar_jugador(email=None, telefono=None):
    """Busca una persona ya cargada, por email o por teléfono.

    Mira también los jugadores que creó el organizador: si el tipo ya está en la
    base como dummy, queremos ENGANCHAR esa cuenta (con su historial de partidos)
    y no crear una nueva en paralelo.

    Ante la duda NO engancha y devuelve None: el alta crea una cuenta nueva.
    Equivocarse para el otro lado es peor — un duplicado se fusiona después con
    la herramienta que ya existe, pero anotar a la persona equivocada le filtra
    su teléfono y su mail a un desconocido.

    Se excluyen las cuentas ya fusionadas (`merged_into`): resucitaban un
    duplicado que un admin había unificado. Los dummies SÍ entran (pueden estar
    inactivos), que es justamente a quienes se quiere enganchar.
    """
    User = get_user_model()
    vivos = User.objects.filter(merged_into__isnull=True)

    if email:
        u = vivos.filter(email__iexact=email.strip()).order_by('id').first()
        if u:
            return u

    cola = _cola_telefono(telefono)
    if not cola:
        return None

    candidatos = [
        pk for pk, numero in vivos.exclude(numero_telefono='')
                                  .exclude(numero_telefono__isnull=True)
                                  .values_list('id', 'numero_telefono')
        if _cola_telefono(numero) == cola
    ]
    # Con más de uno no hay forma de saber cuál es: mejor no adivinar.
    if len(candidatos) != 1:
        return None
    return vivos.filter(pk=candidatos[0]).first()


# --------------------------------------------------------------------------
# Coincidencias al dar de alta un jugador
# --------------------------------------------------------------------------

def _clave_nombre(nombre, apellido):
    """Nombre completo normalizado, para comparar sin tildes ni mayúsculas."""
    return ' '.join(_sin_acentos(f"{nombre or ''} {apellido or ''}").lower().split())


def _parecido(a, b):
    from difflib import SequenceMatcher

    return SequenceMatcher(None, a, b).ratio()


# Debajo de esto son dos personas distintas que casualmente se escriben parecido.
PARECIDO_MINIMO = 0.86


def buscar_coincidencias(nombre, apellido, email=None, telefono=None,
                         excluir_id=None, limite=6):
    """Jugadores que probablemente YA sean la persona que se está por crear.

    El organizador carga gente a mano entre partido y partido, y hasta ahora el
    alta no le decía nada: si el jugador ya estaba, se creaba una cuenta
    repetida y el historial de esa persona quedaba partido en dos.

    Devuelve una lista de dicts `{usuario, motivo, seguro}` ordenada por
    confianza. `seguro=True` significa coincidencia dura (mismo mail o mismo
    teléfono): ahí casi seguro es la misma persona.

    La consulta está acotada a propósito —mail exacto, teléfono exacto y
    apellidos que empiezan igual— para no recorrer la base entera en cada alta,
    que es el problema que ya tiene la pantalla de duplicados.
    """
    User = get_user_model()
    vivos = User.objects.filter(
        merged_into__isnull=True, tipo_usuario='PLAYER'
    ).select_related('division')
    if excluir_id:
        vivos = vivos.exclude(pk=excluir_id)

    encontrados = {}

    def sumar(usuario, motivo, seguro):
        previo = encontrados.get(usuario.pk)
        if previo and previo['seguro'] >= seguro:
            return
        encontrados[usuario.pk] = {'usuario': usuario, 'motivo': motivo,
                                   'seguro': seguro}

    # 1. Mismo email: es la misma cuenta, sin vueltas.
    if email:
        for u in vivos.filter(email__iexact=email.strip())[:limite]:
            sumar(u, 'Tiene ese mismo email', 2)

    # 2. Mismo teléfono normalizado.
    cola = _cola_telefono(telefono)
    if cola:
        con_tel = vivos.exclude(numero_telefono='').exclude(
            numero_telefono__isnull=True)
        for u in con_tel:
            if _cola_telefono(u.numero_telefono) == cola:
                sumar(u, 'Tiene ese mismo WhatsApp', 2)

    # 3. Nombre parecido. Se acota por las primeras letras del apellido para no
    #    traer toda la base: quien escribe "Gomez" no matchea con "Rodriguez".
    raiz = _sin_acentos(apellido or '').lower()[:3]
    if len(raiz) >= 3:
        clave_nueva = _clave_nombre(nombre, apellido)
        for u in vivos.filter(Q(apellido__istartswith=raiz))[:200]:
            clave = _clave_nombre(u.nombre, u.apellido)
            if not clave:
                continue
            if clave == clave_nueva:
                sumar(u, 'Ya hay alguien con ese nombre y apellido', 2)
            elif _parecido(clave, clave_nueva) >= PARECIDO_MINIMO:
                sumar(u, f'Se parece mucho a «{u.full_name}»', 1)

    orden = sorted(encontrados.values(),
                   key=lambda c: (-c['seguro'], c['usuario'].pk))
    return orden[:limite]


def activar_cuenta(usuario, email=None, telefono=None, division=None):
    """Convierte un jugador cargado a mano en una cuenta con la que pueda entrar.

    Es el mismo ascenso que hace el alta sin cuenta cuando engancha a un dummy:
    se conserva el id, así que la persona no pierde ni un partido de historial.

    Devuelve la contraseña generada, o None si la cuenta ya era real (a nadie se
    le pisa la contraseña que eligió).
    """
    if not usuario.is_dummy and usuario.is_active:
        # Ya tiene cuenta propia: sólo se completan los datos que falten.
        if email and not (usuario.email or '').strip():
            usuario.email = email.strip()
        if telefono and not (usuario.numero_telefono or '').strip():
            usuario.numero_telefono = telefono.strip()[:20]
        if division and not usuario.division_id:
            usuario.division = division
        usuario.save()
        return None

    password = generar_password(usuario.nombre or 'padel')
    usuario.is_dummy = False
    usuario.is_active = True
    usuario.debe_cambiar_password = True
    if email and (not usuario.email or usuario.email.endswith('@padel.local')):
        usuario.email = email.strip()
    if telefono:
        usuario.numero_telefono = telefono.strip()[:20]
    if division and not usuario.division_id:
        usuario.division = division
    usuario.set_password(password)
    usuario.save()
    return password


def mensaje_credenciales(usuario, password, club=None):
    """Texto del WhatsApp con los datos de acceso, para que el organizador lo mande.

    La app no manda WhatsApp por su cuenta: arma el texto y el organizador toca
    el botón. Mandar la contraseña por chat es aceptable sólo porque es de un
    solo uso: `debe_cambiar_password` obliga a cambiarla al entrar.
    """
    de_quien = f" de {club.nombre}" if club else ""
    if not password:
        return (f"Hola {usuario.nombre}! Ya te tengo cargado en TodoPadel"
                f"{de_quien}. Entrá con tu cuenta de siempre para ver tus "
                f"partidos y estadísticas: https://todopadel.club")
    return (
        f"Hola {usuario.nombre}! Te creé tu cuenta en TodoPadel{de_quien} "
        f"para que veas tus partidos y estadísticas.\n\n"
        f"Entrá en https://todopadel.club con:\n"
        f"Mail: {usuario.email}\n"
        f"Contraseña: {password}\n\n"
        f"Te va a pedir que la cambies la primera vez."
    )
