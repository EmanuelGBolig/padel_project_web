from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Division
from .models import BusquedaCompanero

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()


@override_settings(STORAGES=TEST_STORAGES)
class MatchmakingTests(TestCase):
    """TP-10: 'busco compañero/rival'."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Septima", orden=1)
        self.player = User.objects.create_user(
            email="ana@test.com", password="x",
            nombre="Ana", apellido="Gómez", division=self.division, tipo_usuario="PLAYER",
        )

    def test_listado_publico_200(self):
        resp = self.client.get(reverse("equipos:buscar_companero"))
        self.assertEqual(resp.status_code, 200)

    def test_jugador_publica_busqueda(self):
        self.client.force_login(self.player)
        resp = self.client.post(
            reverse("equipos:publicar_busqueda"),
            {"ciudad": "Rosario", "nota": "Busco para la 7ma"},
        )
        self.assertEqual(resp.status_code, 302)
        b = BusquedaCompanero.objects.get()
        self.assertEqual(b.jugador, self.player)
        self.assertEqual(b.ciudad, "Rosario")
        # La división se autocompleta desde el jugador si no se especifica.
        self.assertEqual(b.division, self.division)

    def test_busqueda_aparece_en_listado(self):
        BusquedaCompanero.objects.create(
            jugador=self.player, division=self.division, ciudad="Rosario", nota="Hola",
        )
        resp = self.client.get(reverse("equipos:buscar_companero"))
        self.assertIn("Ana Gómez", resp.content.decode())


@override_settings(STORAGES=TEST_STORAGES)
class AdminEquipoListTests(TestCase):
    """La vista de admin de equipos tiraba NameError (500) en cada visita:
    filtraba por una variable `division_id` que nunca se definia."""

    def setUp(self):
        from .models import Equipo
        self.division = Division.objects.create(nombre="Cuarta", orden=4)
        self.otra_division = Division.objects.create(nombre="Quinta", orden=5)
        self.admin = User.objects.create_user(
            email="adm@eq.com", password="x", nombre="Ad", apellido="Min",
            genero="OTRO", tipo_usuario="ADMIN")
        j1 = User.objects.create_user(email="e1@t.com", password="x", nombre="J", apellido="Uno", division=self.division)
        j2 = User.objects.create_user(email="e2@t.com", password="x", nombre="J", apellido="Dos", division=self.division)
        self.equipo = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)

    def test_la_lista_carga(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("equipos:admin_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.equipo, list(resp.context["equipos"]))

    def test_filtro_por_division(self):
        self.client.force_login(self.admin)
        resp = self.client.get(
            reverse("equipos:admin_list"), {"division": self.division.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.equipo, list(resp.context["equipos"]))

        resp = self.client.get(
            reverse("equipos:admin_list"), {"division": self.otra_division.pk})
        self.assertNotIn(self.equipo, list(resp.context["equipos"]))
