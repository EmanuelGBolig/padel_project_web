from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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


@override_settings(STORAGES=TEST_STORAGES)
class GestionParejasOrganizadorTests(TestCase):
    """Bug reportado por un organizador: crea una pareja, no figura en el torneo,
    y al recrearla recibe un 500."""

    def setUp(self):
        from accounts.models import Organizacion
        from .models import Equipo
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgPar", alias="orgpar")
        self.organizador = User.objects.create_user(
            email="org@par.com", password="x", nombre="Or", apellido="Ga",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.organizador.organizacion = self.org
        self.organizador.save()
        self.j1 = User.objects.create_user(email="pa@t.com", password="x", nombre="Pa", apellido="Uno", division=self.division)
        self.j2 = User.objects.create_user(email="pb@t.com", password="x", nombre="Pb", apellido="Dos", division=self.division)
        self.equipo = Equipo.objects.create(jugador1=self.j1, jugador2=self.j2, division=self.division)

    def test_organizador_entra_al_listado_de_parejas(self):
        """Antes el listado era ADMIN-only y el organizador quedaba sin salida."""
        self.client.force_login(self.organizador)
        resp = self.client.get(reverse("equipos:admin_list"))
        self.assertEqual(resp.status_code, 200)

    def test_crear_pareja_duplicada_no_tira_500(self):
        """La UniqueConstraint reventaba en IntegrityError sin manejar (500)."""
        self.client.force_login(self.organizador)
        resp = self.client.post(reverse("equipos:crear_pareja"), {
            "jugador1": self.j1.pk,
            "jugador2": self.j2.pk,
            "division": self.division.pk,
            "categoria": "M",
        })
        self.assertEqual(resp.status_code, 200, "Deberia re-renderizar el form con el error")
        self.assertContains(resp, "ya forman la pareja")

    def test_el_form_explica_el_duplicado(self):
        from .forms import PairCreationForm
        form = PairCreationForm(data={
            "jugador1": self.j1.pk, "jugador2": self.j2.pk,
            "division": self.division.pk, "categoria": "M"})
        self.assertFalse(form.is_valid())
        self.assertIn("ya forman la pareja", str(form.errors))

    def test_disolver_libera_a_los_jugadores(self):
        from .models import Equipo
        self.client.force_login(self.organizador)
        resp = self.client.post(
            reverse("equipos:disolver_equipo", kwargs={"pk": self.equipo.pk}))
        self.assertIn(resp.status_code, (301, 302))
        self.equipo.refresh_from_db()
        self.assertFalse(self.equipo.esta_activo)
        # Y ahora si se puede rearmar la pareja
        nuevo = Equipo.objects.create(
            jugador1=self.j1, jugador2=self.j2, division=self.division)
        self.assertTrue(nuevo.esta_activo)

    def test_no_disuelve_si_esta_en_un_torneo_activo(self):
        from torneos.models import Torneo, Inscripcion
        torneo = Torneo.objects.create(
            nombre="En curso", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.EN_JUEGO)
        Inscripcion.objects.create(torneo=torneo, equipo=self.equipo)

        self.client.force_login(self.organizador)
        self.client.post(reverse("equipos:disolver_equipo", kwargs={"pk": self.equipo.pk}))
        self.equipo.refresh_from_db()
        self.assertTrue(
            self.equipo.esta_activo,
            "Se disolvio una pareja que esta jugando un torneo")


@override_settings(STORAGES=TEST_STORAGES)
class InvitacionSinRecargarTests(TestCase):
    """Aceptar o rechazar cambia una cajita, no puede recargar el perfil entero."""

    def setUp(self):
        from .models import Invitation

        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.a = User.objects.create_user(
            email="a@t.com", password="x", nombre="Ana", apellido="A",
            genero="F", division=self.division)
        self.b = User.objects.create_user(
            email="b@t.com", password="x", nombre="Beto", apellido="B",
            genero="M", division=self.division)
        self.inv = Invitation.objects.create(inviter=self.a, invited=self.b)

    def test_aceptar_con_htmx_devuelve_fragmento(self):
        from .models import Invitation

        self.client.force_login(self.b)
        r = self.client.post(
            reverse("equipos:aceptar_invitacion", kwargs={"pk": self.inv.pk}),
            HTTP_HX_REQUEST="true")

        self.assertEqual(r.status_code, 200, "Con htmx no debe redirigir")
        html = r.content.decode()
        self.assertIn("Ya tenés equipo", html)
        # Fragmento, no página entera: no puede venir el <html> del base.
        self.assertNotIn("<!DOCTYPE", html.upper())
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invitation.Status.ACCEPTED)

    def test_rechazar_con_htmx_devuelve_fragmento(self):
        from .models import Invitation

        self.client.force_login(self.b)
        r = self.client.post(
            reverse("equipos:rechazar_invitacion", kwargs={"pk": self.inv.pk}),
            HTTP_HX_REQUEST="true")

        self.assertEqual(r.status_code, 200)
        self.assertIn("rechazada", r.content.decode())
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invitation.Status.REJECTED)

    def test_sin_htmx_sigue_redirigiendo(self):
        # Si el navegador no ejecuta JS, el submit normal tiene que seguir andando.
        self.client.force_login(self.b)
        r = self.client.post(
            reverse("equipos:rechazar_invitacion", kwargs={"pk": self.inv.pk}))
        self.assertEqual(r.status_code, 302)

    def test_los_dos_botones_ocupan_lo_mismo(self):
        # El "Rechazar" se salía de la caja en mobile porque los botones estaban
        # en un flex al lado del nombre. Ahora van en dos columnas iguales.
        self.client.force_login(self.b)
        html = self.client.get(reverse("accounts:perfil")).content.decode()
        self.assertIn('grid grid-cols-2 gap-2', html)
        self.assertIn('btn btn-sm btn-success w-full', html)
        self.assertIn('btn btn-sm btn-error btn-outline w-full', html)


@override_settings(STORAGES=TEST_STORAGES)
class NombreCompletoEquipoTests(TestCase):
    """En las listas de gestion hace falta el nombre y apellido de los dos.

    `Equipo.nombre` es el codigo corto (solo apellidos) porque tiene que entrar
    en una celda del cuadro; en la lista de inscriptos eso no alcanza para
    identificar a nadie.
    """

    def setUp(self):
        from .models import Equipo

        User = get_user_model()
        self.division = Division.objects.create(nombre="Quinta NC", orden=5)
        self.gonzalo = User.objects.create_user(
            email="gonzalo@t.com", password="x", nombre="Gonzalo",
            apellido="Reina", division=self.division)
        self.dante = User.objects.create_user(
            email="dante@t.com", password="x", nombre="Dante",
            apellido="Esquivel", division=self.division)
        self.equipo = Equipo.objects.create(
            jugador1=self.gonzalo, jugador2=self.dante, division=self.division)

    def test_el_nombre_corto_sigue_siendo_solo_apellidos(self):
        # No se toca: es lo que entra en el cuadro y en la tabla de posiciones.
        self.assertEqual(self.equipo.nombre, "Esquivel/Reina")

    def test_nombre_completo_trae_los_dos_nombres_y_apellidos(self):
        completo = self.equipo.nombre_completo
        for parte in ("Gonzalo", "Reina", "Dante", "Esquivel"):
            self.assertIn(parte, completo)
        self.assertIn(" y ", completo)

    def test_si_falta_el_nombre_no_queda_vacio(self):
        from .models import Equipo

        User = get_user_model()
        sin_nombre = User.objects.create_user(
            email="solo.apellido@t.com", password="x", nombre="",
            apellido="Perez", division=self.division)
        otro = User.objects.create_user(
            email="otro.nc@t.com", password="x", nombre="Ana",
            apellido="Lopez", division=self.division)
        equipo = Equipo.objects.create(
            jugador1=sin_nombre, jugador2=otro, division=self.division)
        self.assertIn("Perez", equipo.nombre_completo)
        self.assertIn("Ana Lopez", equipo.nombre_completo)
