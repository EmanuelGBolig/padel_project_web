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

    def test_home_muestra_cta_para_anonimo(self):
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("/para-organizadores/", resp.content.decode())

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
