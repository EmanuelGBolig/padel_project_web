from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Division, Organizacion
from .forms import OrganizacionForm

# Storage estático plano: en tests no hay manifest de WhiteNoise (collectstatic).
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()


class OrganizacionWhatsappTests(TestCase):
    """TP-02: campo whatsapp + normalización para wa.me."""

    def test_whatsapp_numero_solo_digitos(self):
        org = Organizacion(nombre="Club X", alias="club-x", whatsapp="+54 9 11 2345-6789")
        self.assertEqual(org.whatsapp_numero, "5491123456789")

    def test_whatsapp_numero_vacio(self):
        org = Organizacion(nombre="Club Y", alias="club-y")
        self.assertEqual(org.whatsapp_numero, "")

    def test_form_incluye_whatsapp(self):
        self.assertIn("whatsapp", OrganizacionForm().fields)


@override_settings(STORAGES=TEST_STORAGES)
class PublicProfilePublicAccessTests(TestCase):
    """TP-06: el perfil del jugador es público (sin login) y compartible."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Septima", orden=1)
        self.jugador = User.objects.create_user(
            email="jug@test.com", password="x",
            nombre="Juan", apellido="Pérez", division=self.division,
        )
        self.url = reverse("accounts:detalle", kwargs={"pk": self.jugador.pk})

    def test_perfil_accesible_sin_login(self):
        # Antes redirigía a login (302); ahora debe responder 200 sin sesión.
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_perfil_tiene_boton_compartir_y_og(self):
        resp = self.client.get(self.url)
        html = resp.content.decode()
        self.assertIn("data-share", html)
        self.assertIn('property="og:title"', html)
        self.assertIn("Juan Pérez", html)
