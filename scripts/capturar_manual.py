"""Captura TODAS las pantallas del manual de usuario, por rol.

Recorre la app logueado como jugador, organizador y admin, y guarda una captura
por pantalla en docs/manual/img/<rol>/. Las URLs se resuelven con reverse(),
así el script no se rompe si cambia un path.

Requiere:
    python scripts/datos_demo_manual.py      (una vez, para el elenco de vitrina)
    python manage.py runserver 8010 --noreload   (en otra terminal)

Uso:  python scripts/capturar_manual.py [seccion]
      seccion opcional: jugador | organizador | admin (sin argumento: todas)
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
# Playwright sync corre dentro de un event loop y Django se niega a tocar la BD
# ahí. Es un script de capturas, no un server: el flag es inofensivo acá.
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from django.urls import reverse  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from accounts.models import CustomUser  # noqa: E402

BASE = 'http://localhost:8010'
SALIDA = os.path.join('docs', 'manual', 'img')

T_ABIERTO = 3    # Abierto Demo: con precio, seña y cupos
T_EN_JUEGO = 2   # 24 parejas: zonas completas + llave

JUGADOR_DEMO = 'demo.informe@todopadel.club'      # invitación + notificaciones
JUGADOR_EQUIPO = 'jugador1a@ejemplo.com'          # con equipo e historial
CLAVES = {
    JUGADOR_DEMO: 'DemoInforme2026',
    JUGADOR_EQUIPO: 'ManualDemo2026',
    'organizador.demo@todopadel.club': 'OrganizadorDemo2026',
    'admin.demo@todopadel.club': 'AdminDemo2026',
}

# Los elementos pegados (navbar, barra inferior) se repiten por el medio de una
# captura full_page: se vuelven estáticos sólo para la foto.
SIN_PEGADOS = """
    header, nav, .navbar, .btm-nav,
    [class*="sticky"], [class*="fixed"] {
        position: static !important;
    }
"""


class Camara:
    def __init__(self, ctx, carpeta):
        self.pag = ctx.new_page()
        self.carpeta = os.path.join(SALIDA, carpeta)
        os.makedirs(self.carpeta, exist_ok=True)

    def ir(self, url_name=None, args=None, path=None, espera=900):
        destino = path if path else reverse(url_name, args=args or [])
        self.pag.goto(f'{BASE}{destino}', wait_until='networkidle')
        self.pag.wait_for_timeout(espera)
        return self.pag

    def entrar(self, email):
        # Si quedó una sesión anterior, el login redirige y no hay formulario.
        self.pag.context.clear_cookies()
        self.ir(path='/accounts/login/')
        self.pag.fill('input[name=username]', email)
        self.pag.fill('input[name=password]', CLAVES[email])
        self.pag.click('form button.btn-primary')
        self.pag.wait_for_load_state('networkidle')
        # Sin banners de "subí tu foto" / "formá tu pareja": tapan lo que se
        # quiere mostrar y el lector los puede descartar igual que acá.
        self.pag.evaluate("""
            sessionStorage.setItem('dismissed_banner-foto', '1');
            sessionStorage.setItem('dismissed_banner-equipo', '1');
            sessionStorage.setItem('dismissed_banner-registro', '1');
        """)

    def foto(self, nombre, desc, *, completa=True, recorte=None, scroll=0,
             quieto=True):
        if scroll:
            self.pag.evaluate(f'window.scrollTo(0, {scroll})')
            self.pag.wait_for_timeout(400)
        if quieto and completa and not recorte:
            self.pag.add_style_tag(content=SIN_PEGADOS)
            self.pag.wait_for_timeout(300)
        ruta = os.path.join(self.carpeta, nombre)
        try:
            if recorte:
                self.pag.locator(recorte).first.screenshot(path=ruta)
            else:
                self.pag.screenshot(path=ruta, full_page=completa)
            print(f'  OK  {nombre:<30} {os.path.getsize(ruta)//1024:>4} KB  {desc}')
        except Exception as e:
            print(f'  --  {nombre:<30} FALLO: {str(e)[:90]}')

    def cerrar(self):
        self.pag.close()


def seccion_jugador(ctx):
    print('=== JUGADOR (390x844) ===')
    c = Camara(ctx, 'jugador')

    # --- Sin cuenta ---
    c.ir(path='/')
    c.foto('j01-home.png', 'La pantalla de inicio')
    c.ir(path='/instalar/')
    c.foto('j02-instalar.png', 'Instalar la app en el celular')
    c.ir(path='/accounts/registro/')
    c.foto('j03-registro.png', 'Crear una cuenta')
    c.ir(path='/accounts/login/')
    c.foto('j04-login.png', 'Entrar a la cuenta')
    c.ir('torneos:abierto_list')
    c.foto('j05-torneos.png', 'Torneos abiertos, con filtros')
    c.ir('torneos:detail', [T_ABIERTO])
    c.foto('j06-ficha.png', 'La ficha de un torneo abierto')
    c.ir('torneos:inscribirse_sin_cuenta', [T_ABIERTO])
    c.foto('j07-alta-paso1.png', 'Anotarse sin cuenta: paso 1', recorte='.card')
    c.pag.fill('input[name=nombre]', 'Emanuel')
    c.pag.fill('input[name=apellido]', 'Gomez')
    c.pag.fill('input[name=email]', 'emanuel.demo@mail.com')
    c.pag.fill('input[name=telefono]', '+54 9 223 555-0001')
    c.pag.click('#alta-siguiente')
    c.pag.wait_for_timeout(600)
    c.foto('j08-alta-paso2.png', 'Anotarse sin cuenta: paso 2', recorte='.card')

    # Públicas: el torneo terminado (con campeones) y el circuito.
    from torneos.models import Circuito, Torneo
    t_fi = Torneo.objects.filter(estado='FI').order_by('-pk').first()
    if t_fi:
        c.ir('torneos:detail', [t_fi.pk])
        c.foto('j22-torneo-finalizado.png', 'La ficha de un torneo terminado')
    circ = Circuito.objects.first()
    if circ:
        c.ir('torneos:circuito_detail', [circ.pk])
        c.foto('j23-circuito.png', 'Un circuito con sus fechas')

    # --- Logueado: jugador con equipo e historial ---
    c.entrar(JUGADOR_EQUIPO)
    c.ir('torneos:mis_torneos')
    c.foto('j09-mis-torneos.png', 'Mis torneos')
    c.ir('equipos:mi_equipo')
    c.foto('j10-mi-equipo.png', 'Mi equipo')
    c.ir('equipos:buscar_companero')
    c.foto('j11-buscar-companero.png', 'Búsqueda de compañero')
    c.ir('accounts:perfil')
    c.foto('j12-perfil.png', 'Mi perfil, con estadísticas')
    c.ir('accounts:rankings_jugadores')
    c.foto('j13-rankings.png', 'El ranking de jugadores')
    c.ir('torneos:detail', [T_EN_JUEGO])
    c.foto('j14-torneo-en-juego.png', 'Un torneo en juego: zonas y llave')
    c.ir('torneos:vivo', [T_EN_JUEGO])
    c.foto('j15-vivo.png', 'El torneo en vivo')
    c.ir('torneos:programacion', [T_EN_JUEGO])
    c.foto('j16-horarios.png', 'Los horarios del torneo')
    jugador = CustomUser.objects.get(email=JUGADOR_EQUIPO)
    c.ir('torneos:placa_jugador', [jugador.pk])
    c.foto('j17-placa-jugador.png', 'La placa del jugador para redes')
    # Anotarse CON cuenta y pareja formada: la confirmación de un toque.
    c.ir('torneos:inscribirse', [T_ABIERTO])
    c.foto('j20-inscribirse-cuenta.png', 'Anotarse con cuenta y pareja')

    # --- El jugador demo: invitación + notificaciones ---
    c.entrar(JUGADOR_DEMO)
    c.ir('accounts:perfil')
    c.foto('j18-invitacion.png', 'Invitación de pareja en el perfil',
           recorte='#invitaciones-recibidas')
    c.ir('accounts:notificaciones')
    c.foto('j19-notificaciones.png', 'El panel de notificaciones')
    # Sin pareja formada: elegir o invitar compañero al anotarse.
    c.ir('torneos:inscribirse_con_companero', [T_ABIERTO])
    c.foto('j21-elegir-companero.png', 'Anotarse eligiendo compañero')
    # El perfil público de OTRO jugador, como lo ve cualquiera.
    c.ir('accounts:detalle', [jugador.pk])
    c.foto('j25-perfil-publico.png', 'El perfil público de un jugador')
    # El cambio de contraseña obligatorio tras el alta sin cuenta: se prende
    # la marca, la app redirige sola, y se apaga al terminar.
    demo = CustomUser.objects.get(email=JUGADOR_DEMO)
    demo.debe_cambiar_password = True
    demo.save(update_fields=['debe_cambiar_password'])
    try:
        c.ir(path='/')
        c.foto('j24-cambiar-password.png', 'Cambio de contraseña al primer ingreso')
    finally:
        demo.debe_cambiar_password = False
        demo.save(update_fields=['debe_cambiar_password'])
    c.cerrar()


def seccion_organizador(ctx):
    print('=== ORGANIZADOR (1280x820) ===')
    c = Camara(ctx, 'organizador')
    c.entrar('organizador.demo@todopadel.club')

    c.ir('torneos:dashboard')
    c.foto('o01-dashboard.png', 'El panel del organizador')
    c.ir('torneos:admin_list')
    c.foto('o02-listado.png', 'Mis torneos (gestión)')
    c.ir('torneos:admin_crear')
    c.foto('o03-crear-torneo.png', 'Crear un torneo')
    c.ir('torneos:admin_manage', [T_ABIERTO])
    c.foto('o04-gestion-abierto.png', 'Gestión de un torneo abierto')
    c.ir('torneos:admin_manage', [T_EN_JUEGO])
    c.foto('o05-gestion-en-juego.png', 'Gestión de un torneo en juego')
    c.ir('torneos:cobros', [T_ABIERTO])
    c.foto('o06-cobros.png', 'El panel de cobros')
    c.ir('equipos:crear_pareja')
    c.foto('o07-crear-pareja.png', 'Cargar una pareja a mano')
    c.ir('accounts:crear_dummy_user')
    c.foto('o08-crear-jugador.png', 'Cargar un jugador sin cuenta')
    c.ir('torneos:programacion', [T_EN_JUEGO])
    c.foto('o09-horarios.png', 'La planilla de horarios (con botón PDF)')
    c.ir('torneos:placa', [T_ABIERTO])
    c.foto('o10-placa-torneo.png', 'La placa del torneo para redes')
    org = CustomUser.objects.get(email='organizador.demo@todopadel.club').organizacion
    c.ir('accounts:organizacion_programacion', [org.pk])
    c.foto('o11-prog-general.png', 'Programación general del club')
    c.ir('accounts:organizacion_settings')
    c.foto('o12-ajustes.png', 'Ajustes de la organización (datos de pago)')
    c.ir('accounts:organizacion_sponsors')
    c.foto('o13-sponsors.png', 'Sponsors del club')
    c.ir('torneos:embudo')
    c.foto('o14-embudo.png', 'El embudo de inscripción')
    c.ir('torneos:americano_list')
    c.foto('o15-americanos.png', 'Torneos americanos')
    c.ir('torneos:formatos_list')
    c.foto('o16-formatos.png', 'Formatos de llave personalizados')
    c.ir('torneos:admin_editar', [T_ABIERTO])
    c.foto('o17-editar-torneo.png', 'La configuración de un torneo ya creado')
    c.ir('torneos:formato_crear')
    c.foto('o18-formato-nuevo.png', 'Definir un formato de llave propio')
    c.ir('torneos:americano_crear')
    c.foto('o19-americano-crear.png', 'Armar un americano')
    c.cerrar()


def seccion_admin(ctx):
    print('=== ADMIN (1280x820) ===')
    c = Camara(ctx, 'admin')
    c.entrar('admin.demo@todopadel.club')

    c.ir('accounts:duplicados')
    c.foto('a01-duplicados.png', 'Posibles cuentas duplicadas')
    c.ir('accounts:merge_usuarios')
    c.foto('a02-fusion.png', 'Fusionar dos cuentas')
    jugador = CustomUser.objects.get(email=JUGADOR_EQUIPO)
    c.ir('accounts:admin_user_edit', [jugador.pk])
    c.foto('a03-editar-jugador.png', 'Editar los datos de un jugador')
    c.ir('equipos:admin_list')
    c.foto('a04-equipos.png', 'Listado de parejas (disolver)')
    c.ir('torneos:circuito_admin_list')
    c.foto('a05-circuitos.png', 'Gestión de circuitos')
    c.ir('torneos:revisar_torneos')
    c.foto('a06-revisar.png', 'Diagnóstico de torneos')
    c.cerrar()


def main():
    solo = sys.argv[1] if len(sys.argv) > 1 else None
    with sync_playwright() as p:
        nav = p.chromium.launch()
        movil = nav.new_context(viewport={'width': 390, 'height': 844},
                                color_scheme='dark', device_scale_factor=2)
        escritorio = nav.new_context(viewport={'width': 1280, 'height': 820},
                                     color_scheme='dark', device_scale_factor=1.5)
        if solo in (None, 'jugador'):
            seccion_jugador(movil)
        if solo in (None, 'organizador'):
            seccion_organizador(escritorio)
        if solo in (None, 'admin'):
            seccion_admin(escritorio)
        nav.close()
    print(f'\nCapturas en: {os.path.abspath(SALIDA)}')


if __name__ == '__main__':
    main()
