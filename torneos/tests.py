from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Torneo

# En tests no hay manifest de WhiteNoise (no se corre collectstatic), así que usamos
# el storage estático plano para que {% static %} no falle al renderizar.
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=TEST_STORAGES)
class ShareButtonTorneoDetailTests(TestCase):
    """TP-01: botón de compartir + meta tags Open Graph dinámicos en la ficha."""

    def setUp(self):
        self.torneo = Torneo.objects.create(
            nombre="Apertura Test",
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=3),
            cupos_totales=16,
        )
        self.url = reverse("torneos:detail", kwargs={"pk": self.torneo.pk})

    def test_ficha_muestra_boton_compartir(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Contenedor del partial reutilizable y sus acciones.
        self.assertIn("data-share", html)
        self.assertIn("js-share-copy", html)
        # Link de WhatsApp (funciona sin JS) con el nombre del torneo URL-encoded.
        self.assertIn("https://wa.me/?text=", html)
        self.assertIn("Apertura%20Test", html)

    def test_og_tags_dinamicos_por_torneo(self):
        resp = self.client.get(self.url)
        html = resp.content.decode()
        # og:title refleja el nombre del torneo (no el genérico de base.html).
        self.assertIn('property="og:title"', html)
        self.assertIn("Apertura Test — TodoPadel", html)
        # og:image absoluta apuntando a la imagen por defecto (sin foto_campeones).
        self.assertIn("http://testserver/static/img/og-image.jpg", html)

    def test_share_url_es_absoluta(self):
        resp = self.client.get(self.url)
        html = resp.content.decode()
        self.assertIn('data-share-url="http://testserver', html)
