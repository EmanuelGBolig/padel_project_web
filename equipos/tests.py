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
        # Jugadores cargados por el propio organizador: por eso son de su club.
        # Sin esto la pareja no tiene NINGÚN vínculo con la organización, y el
        # test pasaba a consagrar el agujero que arregla `DisolverEquipoView`
        # (un organizador disolviendo la pareja de dos jugadores ajenos).
        self.j1 = User.objects.create_user(email="pa@t.com", password="x", nombre="Pa", apellido="Uno", division=self.division, organizacion=self.org)
        self.j2 = User.objects.create_user(email="pb@t.com", password="x", nombre="Pb", apellido="Dos", division=self.division, organizacion=self.org)
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

@override_settings(STORAGES=TEST_STORAGES)
class DisolverParejaAjenaTests(TestCase):
    """Un ORGANIZER sólo puede disolver parejas de SU club.

    `Equipo` no tiene FK a organización: la pertenencia se deduce de haber jugado
    un torneo del club, o de que alguno de los dos jugadores sea miembro del club
    (los que carga el propio organizador). Antes alcanzaba con el pk.
    """

    def setUp(self):
        from accounts.models import Organizacion
        from .models import Equipo

        self.division = Division.objects.create(nombre="Cuarta", orden=4)
        self.org_a = Organizacion.objects.create(nombre="Club A", alias="club-a")
        self.org_b = Organizacion.objects.create(nombre="Club B", alias="club-b")

        self.org_user_a = User.objects.create_user(
            email="oa@eq.com", password="x", nombre="Or", apellido="A",
            genero="OTRO", tipo_usuario="ORGANIZER", organizacion=self.org_a)
        self.sin_club = User.objects.create_user(
            email="sc@eq.com", password="x", nombre="Sin", apellido="Club",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.admin = User.objects.create_user(
            email="ad@eq.com", password="x", nombre="Ad", apellido="Min",
            genero="OTRO", tipo_usuario="ADMIN")

        def par(pref, org=None):
            j1 = User.objects.create_user(
                email=f"{pref}1@eq.com", password="x", nombre="N", apellido=pref,
                division=self.division, organizacion=org)
            j2 = User.objects.create_user(
                email=f"{pref}2@eq.com", password="x", nombre="M", apellido=pref,
                division=self.division, organizacion=org)
            return Equipo.objects.create(
                jugador1=j1, jugador2=j2, division=self.division)

        # Dos jugadores que se registraron solos: no son de ningún club.
        self.pareja_ajena = par("aj")
        # Jugadores cargados por el organizador del club A.
        self.pareja_de_a = par("mj", self.org_a)
        # Jugadores del club B.
        self.pareja_de_b = par("db", self.org_b)
        # Sin club, pero con historial en un torneo ya finalizado del club A.
        self.pareja_historica = par("ja")

    def _torneo(self, nombre, org, estado):
        from torneos.models import Torneo
        return Torneo.objects.create(
            nombre=nombre, division=self.division, organizacion=org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=estado)

    def _disolver(self, equipo):
        return self.client.post(
            reverse("equipos:disolver_equipo", kwargs={"pk": equipo.pk}))

    def test_no_disuelve_la_pareja_de_otro_club(self):
        self.client.force_login(self.org_user_a)
        resp = self._disolver(self.pareja_de_b)
        self.assertEqual(resp.status_code, 404)
        self.pareja_de_b.refresh_from_db()
        self.assertTrue(
            self.pareja_de_b.esta_activo,
            "Un organizador disolvio la pareja de otro club")

    def test_no_disuelve_una_pareja_sin_ningun_vinculo(self):
        """Dos jugadores que se anotaron solos no son de ningun organizador."""
        self.client.force_login(self.org_user_a)
        resp = self._disolver(self.pareja_ajena)
        self.assertEqual(resp.status_code, 404)
        self.pareja_ajena.refresh_from_db()
        self.assertTrue(self.pareja_ajena.esta_activo)

    def test_organizador_sin_club_no_disuelve_nada(self):
        self.client.force_login(self.sin_club)
        resp = self._disolver(self.pareja_ajena)
        self.assertEqual(resp.status_code, 404)
        self.pareja_ajena.refresh_from_db()
        self.assertTrue(self.pareja_ajena.esta_activo)

    def test_si_disuelve_la_pareja_de_sus_jugadores(self):
        """Control: el caso que el organizador necesita (cargo mal una pareja)."""
        self.client.force_login(self.org_user_a)
        resp = self._disolver(self.pareja_de_a)
        self.assertIn(resp.status_code, (301, 302))
        self.pareja_de_a.refresh_from_db()
        self.assertFalse(self.pareja_de_a.esta_activo)

    def test_si_disuelve_la_pareja_que_jugo_su_torneo(self):
        """Control: sin club, pero con historial en un torneo del club A."""
        from torneos.models import Inscripcion, Torneo
        torneo = self._torneo("A viejo", self.org_a, Torneo.Estado.FINALIZADO)
        Inscripcion.objects.create(torneo=torneo, equipo=self.pareja_historica)
        self.client.force_login(self.org_user_a)
        resp = self._disolver(self.pareja_historica)
        self.assertIn(resp.status_code, (301, 302))
        self.pareja_historica.refresh_from_db()
        self.assertFalse(self.pareja_historica.esta_activo)

    def test_dos_inscripciones_del_club_no_duplican_la_pareja(self):
        """El OR entra por un join: sin .distinct() hay fila repetida y 500."""
        from torneos.models import Inscripcion, Torneo
        for i in range(2):
            t = self._torneo(f"A viejo {i}", self.org_a, Torneo.Estado.FINALIZADO)
            Inscripcion.objects.create(torneo=t, equipo=self.pareja_historica)

        self.client.force_login(self.org_user_a)
        resp = self.client.get(reverse("equipos:admin_list"))
        self.assertEqual(resp.status_code, 200)
        equipos = list(resp.context["equipos"])
        self.assertEqual(
            equipos.count(self.pareja_historica), 1,
            "La pareja sale repetida en el listado: falta el .distinct()")

        resp = self._disolver(self.pareja_historica)
        self.assertIn(
            resp.status_code, (301, 302),
            "get_object_or_404 revento con MultipleObjectsReturned")
        self.pareja_historica.refresh_from_db()
        self.assertFalse(self.pareja_historica.esta_activo)

    def test_el_listado_no_muestra_parejas_de_otro_club(self):
        self.client.force_login(self.org_user_a)
        resp = self.client.get(reverse("equipos:admin_list"))
        self.assertEqual(resp.status_code, 200)
        equipos = list(resp.context["equipos"])
        self.assertIn(self.pareja_de_a, equipos)
        self.assertNotIn(self.pareja_de_b, equipos)
        self.assertNotIn(self.pareja_ajena, equipos)

    def test_admin_sigue_viendo_y_disolviendo_todo(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("equipos:admin_list"))
        self.assertIn(self.pareja_de_b, list(resp.context["equipos"]))
        resp = self._disolver(self.pareja_de_b)
        self.assertIn(resp.status_code, (301, 302))
        self.pareja_de_b.refresh_from_db()
        self.assertFalse(self.pareja_de_b.esta_activo)
