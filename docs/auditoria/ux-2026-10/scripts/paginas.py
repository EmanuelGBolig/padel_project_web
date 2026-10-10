# -*- coding: utf-8 -*-
"""Lista compartida de paginas y cuentas para las auditorias del sistema de diseno."""

BASE = 'http://localhost:8010'

CUENTAS = {
    'jugador': ('jugador1a@ejemplo.com', 'ManualDemo2026'),
    'organizador': ('organizador.demo@todopadel.club', 'OrganizadorDemo2026'),
    'admin': ('admin.demo@todopadel.club', 'AdminDemo2026'),
}

# (rol, ruta, nombre)
PAGINAS = [
    (None, '/', 'Home'),
    (None, '/torneos/abiertos/', 'Torneos abiertos'),
    (None, '/torneos/en-juego/', 'Torneos en juego'),
    (None, '/torneos/finalizados/', 'Torneos finalizados'),
    (None, '/torneos/2/', 'Ficha de torneo'),
    (None, '/torneos/2/vivo/', 'Torneo en vivo'),
    (None, '/torneos/2/programacion/', 'Planilla de horarios'),
    (None, '/torneos/circuitos/', 'Circuitos'),
    (None, '/accounts/rankings/', 'Ranking de jugadores'),
    (None, '/accounts/organizadores/', 'Clubes'),
    (None, '/accounts/login/', 'Login'),
    (None, '/accounts/registro/', 'Registro'),
    (None, '/instalar/', 'Instalar la app'),
    (None, '/para-organizadores/', 'Landing organizadores'),
    (None, '/torneos/3/anotarme-sin-cuenta/', 'Alta sin cuenta'),
    ('jugador', '/accounts/perfil/', 'Perfil'),
    ('jugador', '/accounts/notificaciones/', 'Notificaciones'),
    ('jugador', '/equipos/mi-equipo/', 'Mi pareja'),
    ('jugador', '/equipos/buscar-companero/', 'Buscar companero'),
    ('jugador', '/torneos/mis-torneos/', 'Mis torneos'),
    ('jugador', '/equipos/crear/', 'Crear pareja'),
    ('organizador', '/torneos/admin/dashboard/', 'Dashboard org'),
    ('organizador', '/torneos/admin/listado/', 'Listado admin'),
    ('organizador', '/torneos/admin/crear/', 'Crear torneo'),
    ('organizador', '/torneos/admin/2/gestionar/', 'Gestion en juego'),
    ('organizador', '/torneos/admin/3/gestionar/', 'Gestion abierto'),
    ('organizador', '/torneos/admin/3/cobros/', 'Cobros'),
    ('organizador', '/torneos/admin/formatos/', 'Formatos'),
    ('organizador', '/torneos/admin/embudo/', 'Embudo'),
    ('organizador', '/accounts/organizacion/ajustes/', 'Ajustes club'),
    ('organizador', '/accounts/organizador/crear-jugador-dummy/', 'Crear jugador'),
    ('organizador', '/equipos/organizador/crear-pareja/', 'Crear pareja (org)'),
    ('admin', '/equipos/admin/listado/', 'Parejas admin'),
    ('admin', '/accounts/usuarios/duplicados/', 'Duplicados'),
    ('admin', '/accounts/usuarios/merge/', 'Fusionar cuentas'),
]


def hacer_sesion(nav, rol, viewport, tema=None, color_scheme='light'):
    ctx = nav.new_context(viewport=viewport, color_scheme=color_scheme)
    pg = ctx.new_page()
    pg.goto(f'{BASE}/accounts/login/', wait_until='domcontentloaded')
    if tema:
        pg.evaluate("t => localStorage.setItem('theme', t)", tema)
    if rol is not None:
        email, clave = CUENTAS[rol]
        pg.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
        pg.fill('input[name=username]', email)
        pg.fill('input[name=password]', clave)
        pg.click('form button.btn-primary')
        pg.wait_for_load_state('networkidle')
    return pg
