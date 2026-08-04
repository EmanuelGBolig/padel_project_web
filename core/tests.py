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
