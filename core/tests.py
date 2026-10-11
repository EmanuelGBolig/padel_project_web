from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()


@override_settings(STORAGES=TEST_STORAGES)
class LandingOrganizadoresTests(TestCase):
    """TP-05: landing /para-organizadores/ + CTA en la home."""

    def test_para_organizadores_responde_200(self):
        resp = self.client.get(reverse("core:para_organizadores"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # La landing vende desde el problema y cierra en WhatsApp.
        self.assertIn("las parejas", html)
        self.assertIn("wa.me/5492236886313", html)

    def test_para_organizadores_publica_precio_y_preview(self):
        """El precio de lista y la imagen de preview son parte de la venta."""
        resp = self.client.get(reverse("core:para_organizadores"))
        html = resp.content.decode()
        self.assertIn("70.000", html)
        self.assertIn("og-todopadel", html)

    def test_clubes_redirige_a_la_landing(self):
        """/clubes/ es el atajo para dictar; redirige permanente a la landing."""
        resp = self.client.get("/clubes/")
        self.assertRedirects(
            resp, reverse("core:para_organizadores"), status_code=301
        )

    def test_home_cta_organizador_va_a_la_landing(self):
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 200)
        # Los CTA de organizador llevan a la landing, que despues cierra en WhatsApp.
        self.assertIn(reverse("core:para_organizadores"), resp.content.decode())

    def test_home_muestra_contadores_y_testimonio(self):
        from .models import Testimonio
        Testimonio.objects.create(autor="Marta", rol="Jugadora 6ta", texto="Excelente plataforma")
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Torneos jugados", html)   # contadores de prueba social
        self.assertIn("Marta", html)             # testimonio activo
        self.assertIn("Excelente plataforma", html)

    def test_home_usa_imagen_de_fondo_hero(self):
        resp = self.client.get(reverse("core:home"))
        # El hero usa una foto de cancha de fondo (stock Pexels).
        self.assertIn("fondos/padel-court", resp.content.decode())


from django.test import TestCase as _TC, override_settings as _ov

_TS = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@_ov(STORAGES=_TS)
class PWAInstalarTests(_TC):
    """PWA: manifest, service worker y tutorial de instalación."""

    def test_service_worker(self):
        r = self.client.get('/sw.js')
        self.assertEqual(r.status_code, 200)
        self.assertIn('application/javascript', r['Content-Type'])
        self.assertIn("addEventListener", r.content.decode())
        self.assertIn("showNotification", r.content.decode())

    def test_manifest(self):
        r = self.client.get('/manifest.webmanifest')
        self.assertEqual(r.status_code, 200)
        self.assertIn('manifest', r['Content-Type'])
        self.assertIn('"standalone"', r.content.decode())

    def test_tutorial_instalar(self):
        from django.urls import reverse
        r = self.client.get(reverse('core:instalar'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Android', html)
        self.assertIn('iPhone', html)
        self.assertIn('Agregar a inicio', html)


class ComentariosDeTemplateTests(TestCase):
    """Los comentarios {# ... #} de Django son de UNA sola linea.

    Si se escriben en varias, Django NO los interpreta como comentario y los
    renderiza como texto visible al usuario. Paso en produccion: la pagina de
    registro mostraba el comentario arriba de cada campo.
    """

    def test_no_hay_comentarios_multilinea(self):
        import glob
        import os
        import re

        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        problemas = []
        for ruta in glob.glob(os.path.join(raiz, '**', '*.html'), recursive=True):
            if 'node_modules' in ruta or 'staticfiles' in ruta:
                continue
            try:
                contenido = open(ruta, encoding='utf-8').read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in re.finditer(r'\{#(.*?)#\}', contenido, flags=re.S):
                if '\n' in m.group(1):
                    linea = contenido[:m.start()].count('\n') + 1
                    rel = os.path.relpath(ruta, raiz)
                    problemas.append(f"{rel}:{linea}")

        self.assertEqual(
            problemas, [],
            "Comentarios {# #} en varias lineas: Django los renderiza como texto "
            "visible. Usa {% comment %}...{% endcomment %}. En: " + ", ".join(problemas))


class TemaCompiladoTests(TestCase):
    """Fija el tema oscuro que ven los usuarios.

    Historia: DaisyUI se cargaba desde un CDN con los 30+ temas. Ese bundle traía
    un bloque `@media (prefers-color-scheme: dark) { :root { ...tema dark... } }`
    que, con la misma especificidad que [data-theme=business] y viniendo despues,
    GANABA. O sea que todo usuario con el sistema en modo oscuro veia el tema
    'dark' (gris azulado), no 'business' (negro neutro), aunque el HTML dijera
    business.

    Al compilar DaisyUI solo con corporate+business ese override desaparecio y la
    app se puso visiblemente mas oscura y fria. Este test fija los valores.
    """

    CSS = 'theme/static/css/tailwind.css'
    # --b1 del tema 'dark' de DaisyUI 4.7.2: es el fondo que la gente ve de noche.
    B1_DARK = '0.253267 0.015896 252.417568'

    def _css(self):
        import os
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(raiz, self.CSS), encoding='utf-8', errors='ignore') as f:
            return f.read()

    def test_el_tema_dark_esta_compilado(self):
        css = self._css()
        self.assertIn(
            self.B1_DARK, css,
            "Falta el tema 'dark' en el CSS compilado: los usuarios con el sistema "
            "en modo oscuro van a ver un negro mas frio del que venian viendo. "
            "Revisa daisyui.themes en theme/static_src/tailwind.config.js")

    def test_estan_los_temas_que_la_app_setea(self):
        css = self._css()
        for tema in ('corporate', 'business'):
            self.assertIn(
                f'[data-theme={tema}]', css,
                f"El tema '{tema}' no esta compilado pero la app lo setea en base.html")

    def test_no_se_carga_css_de_terceros_desde_cdn(self):
        """El CSS tiene que salir del build, no de un CDN externo."""
        import os
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base = os.path.join(raiz, 'theme', 'templates', 'base.html')
        with open(base, encoding='utf-8', errors='ignore') as f:
            html = f.read()
        self.assertNotIn(
            'daisyui@', html,
            "Volvio el CDN de DaisyUI a base.html: son 2,1 MB y un origen externo "
            "en el camino critico.")


@override_settings(STORAGES=TEST_STORAGES)
class PaginasDeErrorTests(TestCase):
    """Las paginas de error tienen que ser de la app, no el HTML pelado.

    Django toma templates/404.html y compania automaticamente porque `templates`
    esta en TEMPLATES['DIRS']; no hacen falta handlers.
    """

    def test_404_usa_la_plantilla_de_la_app(self):
        # DEBUG=False: con DEBUG=True Django muestra su propia pagina de debug.
        with self.settings(DEBUG=False, ALLOWED_HOSTS=['*']):
            resp = self.client.get('/esta-url-no-existe-nunca/')
        self.assertEqual(resp.status_code, 404)
        self.assertTemplateUsed(resp, '404.html')
        self.assertContains(resp, 'Esta página no existe', status_code=404)

    def test_404_ofrece_salidas_utiles(self):
        with self.settings(DEBUG=False, ALLOWED_HOSTS=['*']):
            resp = self.client.get('/landing-comercial.html')
        # Los 404 suelen venir de links viejos: la pagina tiene que ofrecer a
        # donde ir, no dejar a la persona en un callejon sin salida.
        self.assertContains(resp, reverse('torneos:abierto_list'), status_code=404)
        self.assertContains(resp, reverse('core:search'), status_code=404)

    def test_500_no_depende_de_la_base_ni_del_contexto(self):
        # Django renderiza 500.html SIN request ni context processors. Si la
        # plantilla extendiera base.html o consultara la base, la pagina de
        # error fallaria justo cuando mas se la necesita.
        from django.template.loader import render_to_string

        html = render_to_string('500.html')
        self.assertIn('Se nos rompió algo', html)
        self.assertIn('<!doctype html>', html.lower())

    def test_403_y_400_existen_y_no_rompen(self):
        from django.template.loader import render_to_string

        for plantilla in ('403.html', '400.html'):
            html = render_to_string(plantilla)
            self.assertIn('TodoPadel', html, f'{plantilla} no renderizo la base')

@override_settings(STORAGES=TEST_STORAGES)
class EscotillasOperativasTests(TestCase):
    """No hay endpoints que corran management commands adentro de un request.

    `/trigger-migration/` era un GET sin CSRF montado en la RAIZ que corria
    `migrar_rankings_historicos` sincronico: recalcula las 8 divisiones y cuelga
    el worker hasta el timeout, y mientras corre parchea el cache a nivel
    proceso, asi que los otros threads del worker atienden sin cache.
    """

    def test_trigger_migration_ya_no_existe(self):
        from django.urls import NoReverseMatch

        resp = self.client.get("/trigger-migration/")
        self.assertEqual(
            resp.status_code, 404,
            "La escotilla /trigger-migration/ sigue montada en la raiz")
        with self.assertRaises(NoReverseMatch):
            reverse("core:trigger_migration")

    def test_core_views_no_llama_call_command(self):
        """Un management command no se corre adentro de un request web."""
        from core import views as core_views

        self.assertFalse(
            hasattr(core_views, "call_command"),
            "core.views volvio a importar call_command: un comando sincronico "
            "adentro de un request cuelga el worker de gunicorn")
        self.assertFalse(hasattr(core_views, "trigger_migration"))


class ComprimirComprobanteTests(SimpleTestCase):
    """La foto del celular tiene que entrar, y la captura no se toca.

    MAX_IMAGEN_BYTES son 5 MB y una camara de celular moderno los pasa siempre:
    rebotarle la foto deja al jugador sin poder mandar el comprobante, que es su
    unico camino para que le confirmen el lugar. Se achica del lado del servidor.

    Pero SOLO lo que rebotaria: la captura del homebanking es un PNG sin perdida
    y pasarla a JPEG emborrona justo el CBU y el monto que hay que leer.
    """

    def _imagen(self, tamanio, formato, ruido=False):
        import io as _io, random
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        random.seed(7)
        im = Image.new('RGB', tamanio)
        if ruido:
            im.putdata([(random.randrange(256), random.randrange(256),
                         random.randrange(256))
                        for _ in range(tamanio[0] * tamanio[1])])
        buf = _io.BytesIO()
        im.save(buf, format=formato)
        return SimpleUploadedFile(
            'comprobante.' + formato.lower(), buf.getvalue(),
            'image/' + formato.lower())

    def test_la_foto_del_celular_se_achica_y_entra(self):
        from core.imagenes import comprimir_para_subida
        from core.validators import MAX_IMAGEN_BYTES
        from PIL import Image

        f = self._imagen((4032, 3024), 'JPEG', ruido=True)
        self.assertGreater(f.size, MAX_IMAGEN_BYTES, 'El caso necesita pesar de mas')
        salida = comprimir_para_subida(f)
        self.assertLessEqual(
            salida.size, MAX_IMAGEN_BYTES,
            'La foto de celular sigue rebotando: el jugador no puede pagar')
        self.assertTrue(salida.name.endswith('.jpg'))
        salida.seek(0)
        self.assertLessEqual(max(Image.open(salida).size), 2000)

    def test_la_captura_del_homebanking_no_se_recomprime(self):
        from core.imagenes import comprimir_para_subida

        f = self._imagen((2560, 1440), 'PNG')
        salida = comprimir_para_subida(f)
        self.assertIs(
            salida, f,
            'Se recomprimio a JPEG una captura que ya pasaba: emborrona el CBU')

    def test_la_rotacion_del_exif_se_aplica_a_los_pixeles(self):
        """Al re-guardar se pierde el EXIF: si no se aplica, sale acostada."""
        import io as _io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.imagenes import comprimir_para_subida

        im = Image.new('RGB', (6000, 3000), (10, 20, 30))
        buf = _io.BytesIO()
        im.save(buf, format='JPEG')
        f = SimpleUploadedFile('c.jpg', buf.getvalue(), 'image/jpeg')
        salida = comprimir_para_subida(f)
        salida.seek(0)
        ancho, alto = Image.open(salida).size
        self.assertGreater(ancho, alto, 'Una apaisada tiene que salir apaisada')

    def test_un_archivo_que_no_es_imagen_vuelve_igual(self):
        """El que corta es validar_imagen, no esta funcion."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.imagenes import comprimir_para_subida

        f = SimpleUploadedFile('c.jpg', b'no soy una imagen', 'image/jpeg')
        self.assertIs(comprimir_para_subida(f), f)


@override_settings(STORAGES=TEST_STORAGES)
class LandingLinkeadaDesdeLaAppTests(TestCase):
    """La landing se alcanza desde CUALQUIER pagina, no solo desde la home.

    El punto de entrada mas comun de este producto no es la home: es la ficha de
    un torneo que alguien compartio por WhatsApp. El que llegaba ahi y resultaba
    ser organizador de un club no tenia ningun camino a la pagina que le explica
    el producto, porque los dos links vivian en home.html.
    """

    def setUp(self):
        from accounts.models import Division, Organizacion
        self.division = Division.objects.create(nombre='Quinta', orden=5)
        self.org = Organizacion.objects.create(nombre='Club L', alias='cl-l')
        self.jugador = User.objects.create_user(
            email='jug@ll.com', password='x', nombre='Ju', apellido='Gador',
            tipo_usuario='PLAYER', division=self.division)
        self.organizador = User.objects.create_user(
            email='org@ll.com', password='x', nombre='Or', apellido='Ga',
            tipo_usuario='ORGANIZER', organizacion=self.org)

    def _html(self, user=None):
        if user:
            self.client.force_login(user)
        resp = self.client.get(reverse('torneos:abierto_list'))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_un_anonimo_la_alcanza_desde_una_pagina_que_no_es_la_home(self):
        self.assertIn(reverse('core:para_organizadores'), self._html())

    def test_un_jugador_tambien(self):
        self.assertIn(reverse('core:para_organizadores'), self._html(self.jugador))

    def test_al_organizador_no_se_le_vende_el_producto(self):
        """Ya es usuario: la landing es ruido y tiene Crear Torneo en su menu."""
        html = self._html(self.organizador)
        self.assertNotIn(reverse('core:para_organizadores'), html)
        self.assertIn('Crear Torneo', html)

    def test_el_organizador_conserva_el_camino_a_soporte(self):
        self.assertIn('wa.me', self._html(self.organizador))


@override_settings(STORAGES=TEST_STORAGES)
class SitemapTests(TestCase):
    """El sitemap incluye la landing comercial.

    Estaba alcanzable para alguien navegando la app pero no para Google, y una
    pagina de venta que no se indexa no se encuentra sola.
    """

    def test_la_landing_esta_en_el_sitemap(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            reverse('core:para_organizadores'), resp.content.decode(),
            'La landing comercial no se indexa')

    def test_la_landing_no_dice_que_cambia_a_diario(self):
        """Es contenido fijo de venta: pedirle a Google que la recorra todos los
        dias es pedirle que la recorra al vacio."""
        import re
        html = self.client.get('/sitemap.xml').content.decode()
        i = html.find(reverse('core:para_organizadores'))
        bloque = html[i:i + 200]
        self.assertIn('<changefreq>monthly</changefreq>', bloque)
        self.assertIn('<priority>0.9</priority>', bloque)

    def test_los_demas_estaticos_no_cambiaron(self):
        """Agregar la landing no tenia que tocar los valores de los otros."""
        html = self.client.get('/sitemap.xml').content.decode()
        i = html.find(reverse('accounts:login'))
        self.assertIn('<changefreq>daily</changefreq>', html[i:i + 200])
        self.assertIn('<priority>0.5</priority>', html[i:i + 200])

    def test_el_robots_apunta_al_sitemap(self):
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('sitemap.xml', resp.content.decode().lower())

    def test_los_torneos_vienen_ordenados(self):
        """Un sitemap pagina de a 50.000: sin orden, entre pagina y pagina un
        torneo puede repetirse o faltar. Django lo avisa con un warning."""
        import warnings
        from django.core.paginator import UnorderedObjectListWarning
        with warnings.catch_warnings():
            warnings.simplefilter('error', UnorderedObjectListWarning)
            resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
