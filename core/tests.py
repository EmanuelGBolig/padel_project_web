from django.test import TestCase, override_settings
from django.urls import reverse

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class LandingOrganizadoresTests(TestCase):
    """TP-05: landing /para-organizadores/ + CTA en la home."""

    def test_para_organizadores_responde_200(self):
        resp = self.client.get(reverse("core:para_organizadores"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Creá tu torneo", resp.content.decode())

    def test_home_cta_organizador_va_a_whatsapp(self):
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 200)
        # Los CTA de organizador redirigen a WhatsApp del dueño.
        self.assertIn("wa.me/5492236886313", resp.content.decode())

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
