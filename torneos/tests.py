from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Division
from equipos.models import Equipo
from .models import Torneo, Inscripcion, Grupo, EquipoGrupo, PartidoGrupo, Partido

# En tests no hay manifest de WhiteNoise (no se corre collectstatic), así que usamos
# el storage estático plano para que {% static %} no falle al renderizar.
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()


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
        self.assertIn("http://testserver/static/img/og-image.png", html)

    def test_share_url_es_absoluta(self):
        resp = self.client.get(self.url)
        html = resp.content.decode()
        self.assertIn('data-share-url="http://testserver', html)


@override_settings(STORAGES=TEST_STORAGES)
class GenerarBracketZonaIncompletaTests(TestCase):
    """Bugfix: al calcular la llave, las zonas que aún tienen partidos pendientes
    NO deben volcar equipos al cuadro (no clasificaron todavía). Su slot debe
    quedar como placeholder (1A, 2B...) hasta cerrar la zona.

    Reproduce el reporte: con 2 zonas, si solo una está cerrada, antes aparecían
    parejas de la zona incompleta como si ya hubieran clasificado.
    """

    contador = 0

    def _crear_equipo(self, division):
        GenerarBracketZonaIncompletaTests.contador += 1
        n = GenerarBracketZonaIncompletaTests.contador
        j1 = User.objects.create_user(
            email=f"jug{n}a@test.com", password="x",
            nombre=f"Nom{n}A", apellido=f"Ape{n}A", division=division,
        )
        j2 = User.objects.create_user(
            email=f"jug{n}b@test.com", password="x",
            nombre=f"Nom{n}B", apellido=f"Ape{n}B", division=division,
        )
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=division)

    def _partido(self, grupo, e1, e2, ganador):
        gana_e1 = ganador == e1
        return PartidoGrupo.objects.create(
            grupo=grupo, equipo1=e1, equipo2=e2,
            e1_set1=6 if gana_e1 else 2, e2_set1=2 if gana_e1 else 6,
            e1_set2=6 if gana_e1 else 2, e2_set2=2 if gana_e1 else 6,
            e1_sets_ganados=2 if gana_e1 else 0,
            e2_sets_ganados=0 if gana_e1 else 2,
            ganador=ganador,
        )

    def setUp(self):
        self.division = Division.objects.create(nombre="Septima", orden=1)
        self.admin = User.objects.create_user(
            email="admin@test.com", password="x",
            nombre="Admin", apellido="Test", tipo_usuario="ADMIN", is_staff=True,
        )
        self.torneo = Torneo.objects.create(
            nombre="Test Zonas", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=6, estado=Torneo.Estado.EN_JUEGO,
        )
        # 6 parejas inscritas -> get_format(6) usa el formato custom de 2 zonas de 3.
        equipos = [self._crear_equipo(self.division) for _ in range(6)]
        for eq in equipos:
            Inscripcion.objects.create(torneo=self.torneo, equipo=eq)

        a, b = equipos[:3], equipos[3:]
        self.zona_a = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        self.zona_b = Grupo.objects.create(torneo=self.torneo, nombre="Zona B")
        for i, eq in enumerate(a, 1):
            EquipoGrupo.objects.create(grupo=self.zona_a, equipo=eq, numero=i)
        for i, eq in enumerate(b, 1):
            EquipoGrupo.objects.create(grupo=self.zona_b, equipo=eq, numero=i)

        # Zona A: COMPLETA (los 3 partidos con ganador).
        self._partido(self.zona_a, a[0], a[1], ganador=a[0])
        self._partido(self.zona_a, a[0], a[2], ganador=a[0])
        self._partido(self.zona_a, a[1], a[2], ganador=a[1])
        # Zona B: INCOMPLETA (un partido sin ganador).
        self._partido(self.zona_b, b[0], b[1], ganador=b[0])
        self._partido(self.zona_b, b[0], b[2], ganador=b[0])
        self._partido(self.zona_b, b[1], b[2], ganador=None)

    def _generar_bracket(self):
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        return self.client.post(url, {"action": "generar_octavos"})

    def _equipo_en_slot(self, ph):
        """Equipo asignado al slot con placeholder `ph`, sin importar el lado."""
        from django.db.models import Q
        from .models import Partido
        p = Partido.objects.filter(torneo=self.torneo).filter(
            Q(placeholder_e1=ph) | Q(placeholder_e2=ph)).get()
        return p.equipo1 if p.placeholder_e1 == ph else p.equipo2

    def test_zona_completa_llena_slots(self):
        self._generar_bracket()
        self.assertIsNotNone(self._equipo_en_slot("1A"), "1A debería estar lleno (Zona A cerrada)")
        self.assertIsNotNone(self._equipo_en_slot("2A"), "2A debería estar lleno (Zona A cerrada)")

    def test_zona_incompleta_queda_placeholder(self):
        self._generar_bracket()
        # 2B y 1B pertenecen a la Zona B (incompleta) -> NO deben tener equipo.
        self.assertIsNone(self._equipo_en_slot("2B"), "2B NO debe estar lleno: la Zona B no terminó")
        self.assertIsNone(self._equipo_en_slot("1B"), "1B NO debe estar lleno: la Zona B no terminó")


from unittest import skipUnless

try:
    import cloudinary  # noqa: F401
    _CLOUDINARY_AVAILABLE = True
except Exception:  # pragma: no cover
    _CLOUDINARY_AVAILABLE = False


class PlacaCampeonesTests(TestCase):
    """TP-01b: placa de campeones (overlay Cloudinary) y fallbacks seguros."""

    @skipUnless(_CLOUDINARY_AVAILABLE, "cloudinary no instalado")
    def test_build_placa_url_genera_overlays(self):
        import cloudinary
        from .social import build_placa_url
        cloudinary.config(cloud_name="demo", api_key="k", api_secret="s", secure=True)
        url = build_placa_url("torneos/campeones/foto1", "Apertura 7ma", "Gómez/Pérez")
        self.assertIn("res.cloudinary.com/demo", url)
        self.assertIn("l_text", url)                    # hay overlays de texto
        self.assertIn("CAMPEONES", url)                 # etiqueta principal
        self.assertIn("torneos/campeones/foto1", url)   # base = foto de campeones

    def test_cloudinary_inactivo_en_tests(self):
        from .social import cloudinary_activo
        # En tests el storage de media por defecto es FileSystemStorage: la placa
        # NO debe activarse (evita romper local / entornos sin Cloudinary).
        self.assertFalse(cloudinary_activo())

    def test_placa_none_si_torneo_no_finalizado(self):
        from .social import placa_campeones_url
        torneo = Torneo.objects.create(
            nombre="Abierto", fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=8, estado=Torneo.Estado.ABIERTO,
        )
        self.assertIsNone(placa_campeones_url(torneo))


@override_settings(STORAGES=TEST_STORAGES)
class FichaVendedoraTests(TestCase):
    """TP-03: campos de sede/premio/reglamento + cupos restantes en la ficha."""

    def test_cupos_disponibles(self):
        torneo = Torneo.objects.create(
            nombre="Cupos", fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=8,
        )
        self.assertEqual(torneo.cupos_disponibles, 8)

    def test_detalle_muestra_info_vendedora(self):
        torneo = Torneo.objects.create(
            nombre="Copa Sur", estado=Torneo.Estado.ABIERTO, cupos_totales=8,
            fecha_inicio=timezone.now().date() + timedelta(days=10),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=5),
            sede_nombre="Club Norte", ciudad="Mar del Plata",
            premio="Trofeos + indumentaria", reglamento="Al mejor de 3 sets.",
        )
        resp = self.client.get(reverse("torneos:detail", kwargs={"pk": torneo.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Club Norte", html)
        self.assertIn("Mar del Plata", html)
        self.assertIn("Trofeos + indumentaria", html)
        self.assertIn("Reglamento", html)
        # Sin cover_image propia, la ficha usa una foto de cancha por defecto.
        self.assertIn("fondos/padel-court", html)


@override_settings(STORAGES=TEST_STORAGES)
class TorneosPorCiudadTests(TestCase):
    """TP-14: páginas por ciudad + sitemap de ciudades."""

    def _torneo(self, ciudad):
        return Torneo.objects.create(
            nombre=f"Copa {ciudad}", ciudad=ciudad, estado=Torneo.Estado.ABIERTO,
            cupos_totales=8, fecha_inicio=timezone.now().date() + timedelta(days=5),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
        )

    def test_pagina_ciudad_lista_torneos(self):
        self._torneo("Mar del Plata")
        resp = self.client.get(reverse("torneos:ciudad", kwargs={"ciudad": "Mar del Plata"}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Copa Mar del Plata", resp.content.decode())

    def test_sitemap_incluye_ciudad(self):
        self._torneo("Rosario")
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("/torneos/ciudad/Rosario/", resp.content.decode())


@override_settings(STORAGES=TEST_STORAGES)
class TorneoVivoTests(TestCase):
    """TP-13: scoreboard público en vivo."""

    def test_vivo_responde_200(self):
        torneo = Torneo.objects.create(
            nombre="En Juego", estado=Torneo.Estado.EN_JUEGO, cupos_totales=8,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
        )
        resp = self.client.get(reverse("torneos:vivo", kwargs={"pk": torneo.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("En vivo", resp.content.decode())


@override_settings(STORAGES=TEST_STORAGES)
class CircuitoTests(TestCase):
    """TP-12: circuitos con ranking acumulado."""

    contador = 0

    def _user(self, division):
        CircuitoTests.contador += 1
        n = CircuitoTests.contador
        return User.objects.create_user(
            email=f"circ{n}@test.com", password="x",
            nombre=f"N{n}", apellido=f"A{n}", division=division,
        )

    def setUp(self):
        from .models import Circuito
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.e1 = Equipo.objects.create(
            jugador1=self._user(self.division), jugador2=self._user(self.division), division=self.division,
        )
        self.e2 = Equipo.objects.create(
            jugador1=self._user(self.division), jugador2=self._user(self.division), division=self.division,
        )
        self.torneo = Torneo.objects.create(
            nombre="Fecha 1", division=self.division, estado=Torneo.Estado.EN_JUEGO, cupos_totales=8,
            fecha_inicio=timezone.now().date(), fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
        )
        grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        EquipoGrupo.objects.create(grupo=grupo, equipo=self.e1, numero=1)
        EquipoGrupo.objects.create(grupo=grupo, equipo=self.e2, numero=2)
        PartidoGrupo.objects.create(
            grupo=grupo, equipo1=self.e1, equipo2=self.e2, ganador=self.e1,
            e1_sets_ganados=2, e2_sets_ganados=0,
        )
        self.circuito = Circuito.objects.create(nombre="Apertura 2026")
        self.circuito.torneos.add(self.torneo)

    def test_listado_y_detalle_200(self):
        self.assertEqual(self.client.get(reverse("torneos:circuito_list")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("torneos:circuito_detail", kwargs={"pk": self.circuito.pk})).status_code,
            200,
        )

    def test_tabla_acumula_puntos_de_zona(self):
        tabla = self.circuito.tabla_posiciones()
        puntos = {f['jugador'].id: f['puntos'] for f in tabla}
        # Cada jugador de la pareja ganadora suma 15 pts por la victoria de zona.
        self.assertEqual(puntos.get(self.e1.jugador1_id), 15)
        self.assertEqual(puntos.get(self.e1.jugador2_id), 15)


@override_settings(STORAGES=TEST_STORAGES)
class AmericanoTests(TestCase):
    """TP-09: Americano/Mexicano (engine + flujos)."""

    def setUp(self):
        from .models import Americano, JugadorAmericano
        self.admin = User.objects.create_user(
            email="admin-am@test.com", password="x", nombre="Adm", apellido="In",
            tipo_usuario="ADMIN", is_staff=True,
        )
        self.am = Americano.objects.create(nombre="Social del viernes", tipo=Americano.Tipo.AMERICANO, num_canchas=1)
        self.jugadores = [
            JugadorAmericano.objects.create(americano=self.am, nombre=f"J{i}", orden=i)
            for i in range(4)
        ]

    def test_join_publico_crea_jugador(self):
        from .models import Americano, JugadorAmericano
        am2 = Americano.objects.create(nombre="Abierto", tipo=Americano.Tipo.AMERICANO)
        url = reverse("torneos:americano_join", kwargs={"codigo": am2.codigo})
        self.assertEqual(self.client.get(url).status_code, 200)  # público, sin login
        resp = self.client.post(url, {"nombre": "Pedro"})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(JugadorAmericano.objects.filter(americano=am2, nombre="Pedro").exists())

    def test_iniciar_americano_genera_3_rondas_con_rotacion(self):
        from .models import Americano
        self.client.force_login(self.admin)
        url = reverse("torneos:americano_manage", kwargs={"pk": self.am.pk})
        self.client.post(url, {"action": "iniciar"})
        self.am.refresh_from_db()
        self.assertEqual(self.am.estado, Americano.Estado.EN_JUEGO)
        self.assertEqual(self.am.rondas.count(), 3)

        # El jugador J0 debe jugar con cada uno de los otros 3 a lo largo de las rondas.
        j0 = self.jugadores[0].id
        companeros = set()
        from .models import PartidoAmericano
        for p in PartidoAmericano.objects.filter(ronda__americano=self.am):
            equipo_a = {p.a1_id, p.a2_id}
            equipo_b = {p.b1_id, p.b2_id}
            for equipo in (equipo_a, equipo_b):
                if j0 in equipo:
                    companeros |= (equipo - {j0})
        otros = {j.id for j in self.jugadores[1:]}
        self.assertEqual(companeros, otros)

    def test_cargar_resultado_suma_puntos(self):
        self.client.force_login(self.admin)
        url = reverse("torneos:americano_manage", kwargs={"pk": self.am.pk})
        self.client.post(url, {"action": "iniciar"})
        from .models import PartidoAmericano
        partido = PartidoAmericano.objects.filter(ronda__americano=self.am).first()
        self.client.post(url, {
            "action": "cargar_resultado", "partido_id": partido.id,
            "games_a": 6, "games_b": 2,
        })
        partido.refresh_from_db()
        self.assertTrue(partido.cargado)
        # Los del equipo A suman 6, los del B suman 2.
        from .models import JugadorAmericano
        self.assertEqual(JugadorAmericano.objects.get(pk=partido.a1_id).puntos, 6)
        self.assertEqual(JugadorAmericano.objects.get(pk=partido.b1_id).puntos, 2)

    def test_mexicano_genera_1_ronda_y_luego_siguiente(self):
        from .models import Americano
        am = Americano.objects.create(nombre="Mexi", tipo=Americano.Tipo.MEXICANO, num_canchas=1)
        from .models import JugadorAmericano
        for i in range(4):
            JugadorAmericano.objects.create(americano=am, nombre=f"M{i}", orden=i)
        self.client.force_login(self.admin)
        url = reverse("torneos:americano_manage", kwargs={"pk": am.pk})
        self.client.post(url, {"action": "iniciar"})
        self.assertEqual(am.rondas.count(), 1)  # Mexicano arranca con 1 ronda
        self.client.post(url, {"action": "siguiente_ronda"})
        self.assertEqual(am.rondas.count(), 2)


class AmericanoScopingTests(TestCase):
    """Auditoria - critico 1: AmericanoManageView no validaba el club.

    `AdminOrOrganizerMixin` solo mira el ROL, y la vista no acotaba el
    queryset, asi que un organizador podia tomar el pk de un americano ajeno
    (la URL usa el pk, secuencial) y ejecutar todo el POST sobre el.
    """

    def setUp(self):
        from accounts.models import Organizacion
        from .models import Americano, JugadorAmericano

        self.club_a = Organizacion.objects.create(nombre="Club A", alias="club-a")
        self.club_b = Organizacion.objects.create(nombre="Club B", alias="club-b")
        self.org_b = User.objects.create_user(
            email="org-b@test.com", password="x", nombre="Org", apellido="B",
            tipo_usuario="ORGANIZER", organizacion=self.club_b,
        )
        self.admin = User.objects.create_user(
            email="admin-scope@test.com", password="x", nombre="Ad", apellido="Min",
            tipo_usuario="ADMIN", is_staff=True,
        )
        # El americano es del club A; lo va a atacar el organizador del club B.
        self.am_a = Americano.objects.create(
            nombre="Social del club A", tipo=Americano.Tipo.AMERICANO,
            num_canchas=1, organizacion=self.club_a,
        )
        for i in range(4):
            JugadorAmericano.objects.create(americano=self.am_a, nombre="A%d" % i, orden=i)
        self.url = reverse("torneos:americano_manage", kwargs={"pk": self.am_a.pk})

    def test_organizador_de_otro_club_no_puede_ver_el_panel(self):
        self.client.force_login(self.org_b)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_organizador_de_otro_club_no_puede_iniciarlo(self):
        from .models import Americano

        self.client.force_login(self.org_b)
        resp = self.client.post(self.url, {"action": "iniciar"})
        self.assertEqual(resp.status_code, 404)
        self.am_a.refresh_from_db()
        self.assertNotEqual(self.am_a.estado, Americano.Estado.EN_JUEGO)
        self.assertEqual(self.am_a.rondas.count(), 0)

    def test_organizador_de_otro_club_no_puede_finalizarlo(self):
        from .models import Americano

        self.client.force_login(self.org_b)
        resp = self.client.post(self.url, {"action": "finalizar"})
        self.assertEqual(resp.status_code, 404)
        self.am_a.refresh_from_db()
        self.assertNotEqual(self.am_a.estado, Americano.Estado.FINALIZADO)

    def test_el_dueno_si_puede(self):
        from .models import Americano

        duenio = User.objects.create_user(
            email="org-a@test.com", password="x", nombre="Org", apellido="A",
            tipo_usuario="ORGANIZER", organizacion=self.club_a,
        )
        self.client.force_login(duenio)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, {"action": "iniciar"})
        self.am_a.refresh_from_db()
        self.assertEqual(self.am_a.estado, Americano.Estado.EN_JUEGO)

    def test_el_admin_puede_sobre_cualquier_club(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)


class CorreccionResultadoBracketTests(TestCase):
    """Auditoria - critico 2: corregir o borrar un resultado dejaba basura.

    `Partido.save()` solo propagaba el ganador hacia adelante y solo si no era
    nulo, asi que la pareja que ya habia avanzado se quedaba en la ronda
    siguiente, y si esa ronda ya se habia jugado su resultado quedaba en pie
    con un ganador que ya no la jugaba.
    """

    contador = 0

    def _equipo(self):
        CorreccionResultadoBracketTests.contador += 1
        n = CorreccionResultadoBracketTests.contador
        j1 = User.objects.create_user(
            email="br%da@test.com" % n, password="x", nombre="B%dA" % n,
            apellido="X", division=self.division,
        )
        j2 = User.objects.create_user(
            email="br%db@test.com" % n, password="x", nombre="B%dB" % n,
            apellido="Y", division=self.division,
        )
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)

    def setUp(self):
        self.division = Division.objects.create(nombre="Sexta", orden=2)
        self.torneo = Torneo.objects.create(
            nombre="Bracket Test", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=4, estado=Torneo.Estado.EN_JUEGO,
        )
        self.a, self.b, self.c, self.d = [self._equipo() for _ in range(4)]
        # Semis (ronda 1) -> Final (ronda 2). Los impares entran por equipo1.
        self.final = Partido.objects.create(
            torneo=self.torneo, ronda=2, orden_partido=1,
        )
        self.semi1 = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.a, equipo2=self.b, siguiente_partido=self.final,
        )
        self.semi2 = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=2,
            equipo1=self.c, equipo2=self.d, siguiente_partido=self.final,
        )

    def test_cargar_resultado_avanza_al_ganador(self):
        self.semi1.ganador = self.a
        self.semi1.save()
        self.final.refresh_from_db()
        self.assertEqual(self.final.equipo1_id, self.a.id)

    def test_borrar_el_resultado_saca_al_equipo_de_la_ronda_siguiente(self):
        self.semi1.ganador = self.a
        self.semi1.save()
        self.final.refresh_from_db()
        self.assertEqual(self.final.equipo1_id, self.a.id)

        # El organizador se dio cuenta de que habia cargado cualquier cosa.
        self.semi1.limpiar_resultado()

        self.final.refresh_from_db()
        self.assertIsNone(
            self.final.equipo1_id,
            "La pareja quedo metida en la final despues de borrar la semi.",
        )

    def test_corregir_el_ganador_reemplaza_al_que_habia_avanzado(self):
        self.semi1.ganador = self.a
        self.semi1.save()
        self.semi1.ganador = self.b
        self.semi1.save()
        self.final.refresh_from_db()
        self.assertEqual(self.final.equipo1_id, self.b.id)

    def test_corregir_una_semi_con_la_final_ya_jugada_invalida_la_final(self):
        # Se juega todo: A gana su semi, C la otra, y A gana la final.
        self.semi1.ganador = self.a
        self.semi1.save()
        self.semi2.ganador = self.c
        self.semi2.save()
        self.final.refresh_from_db()
        self.final.ganador = self.a
        self.final.resultado = "6-4, 6-2"
        self.final.save()
        self.torneo.refresh_from_db()
        self.assertEqual(self.torneo.ganador_del_torneo_id, self.a.id)

        # Ahora se corrige la semi: en realidad habia ganado B.
        self.semi1.refresh_from_db()
        self.semi1.ganador = self.b
        self.semi1.save()

        self.final.refresh_from_db()
        self.assertEqual(self.final.equipo1_id, self.b.id)
        self.assertIsNone(
            self.final.ganador_id,
            "La final quedo con un ganador que ya no la esta jugando.",
        )
        self.assertFalse(self.final.resultado)

        self.torneo.refresh_from_db()
        self.assertIsNone(
            self.torneo.ganador_del_torneo_id,
            "El torneo quedo con un campeon fantasma.",
        )
        self.assertEqual(self.torneo.estado, Torneo.Estado.EN_JUEGO)

    def test_borrar_la_final_deja_el_torneo_sin_campeon(self):
        self.semi1.ganador = self.a
        self.semi1.save()
        self.final.refresh_from_db()
        self.final.ganador = self.a
        self.final.save()
        self.torneo.refresh_from_db()
        self.assertEqual(self.torneo.estado, Torneo.Estado.FINALIZADO)

        self.final.limpiar_resultado()

        self.torneo.refresh_from_db()
        self.assertIsNone(self.torneo.ganador_del_torneo_id)
        self.assertEqual(self.torneo.estado, Torneo.Estado.EN_JUEGO)


class RecalculoRankingsTests(TestCase):
    """Auditoria - alto: cada resultado disparaba un recalculo completo.

    `invalidar_cache_division` arrancaba un thread por cada save que borraba y
    reconstruia el ranking entero de la division. Cargar una zona de 24
    partidos eran 24 recalculos completos peleandose por la base, y es
    exactamente lo que hace el organizador al borde de la cancha.
    """

    def setUp(self):
        from . import signals

        self.division = Division.objects.create(nombre="Quinta", orden=3)
        # Estado limpio: los tests corren en el mismo proceso.
        with signals._candado_recalculos:
            signals._recalculos_pendientes.clear()

    def tearDown(self):
        from . import signals

        with signals._candado_recalculos:
            for t in signals._recalculos_pendientes.values():
                t.cancel()
            signals._recalculos_pendientes.clear()

    @override_settings(RANKINGS_DEBOUNCE_SEGUNDOS=30)
    def test_una_rafaga_de_resultados_agenda_un_solo_recalculo(self):
        from . import signals

        for _ in range(24):
            signals._programar_recalculo(self.division.id)

        self.assertEqual(
            len(signals._recalculos_pendientes), 1,
            "24 resultados seguidos deberian agendar UN recalculo, no 24.",
        )

    @override_settings(RANKINGS_DEBOUNCE_SEGUNDOS=30)
    def test_divisiones_distintas_no_se_pisan(self):
        from . import signals

        otra = Division.objects.create(nombre="Cuarta", orden=4)
        signals._programar_recalculo(self.division.id)
        signals._programar_recalculo(otra.id)
        self.assertEqual(len(signals._recalculos_pendientes), 2)

    @override_settings(RANKINGS_DEBOUNCE_SEGUNDOS=0)
    def test_en_cero_corre_sincronico(self):
        from unittest.mock import patch

        from . import signals

        with patch.object(signals, 'actualizar_rankings_en_bd') as fake:
            signals._programar_recalculo(self.division.id)
        fake.assert_called_once()
        self.assertEqual(len(signals._recalculos_pendientes), 0)


class TablaPosicionesSinImpactoTests(TestCase):
    """Auditoria - medio: la tabla se recalculaba aunque el save no tocara el resultado.

    Programar el horario de un partido o marcar un recordatorio como enviado
    recomputaba la tabla de posiciones completa del grupo.
    """

    contador = 0

    def _equipo(self):
        TablaPosicionesSinImpactoTests.contador += 1
        n = TablaPosicionesSinImpactoTests.contador
        j1 = User.objects.create_user(
            email="tp%da@test.com" % n, password="x", nombre="T%dA" % n,
            apellido="X", division=self.division,
        )
        j2 = User.objects.create_user(
            email="tp%db@test.com" % n, password="x", nombre="T%dB" % n,
            apellido="Y", division=self.division,
        )
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)

    def setUp(self):
        self.division = Division.objects.create(nombre="Octava", orden=8)
        self.torneo = Torneo.objects.create(
            nombre="Sin impacto", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=4, estado=Torneo.Estado.EN_JUEGO,
        )
        self.grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        self.e1, self.e2 = self._equipo(), self._equipo()
        EquipoGrupo.objects.create(grupo=self.grupo, equipo=self.e1, numero=1)
        EquipoGrupo.objects.create(grupo=self.grupo, equipo=self.e2, numero=2)
        self.partido = PartidoGrupo.objects.create(
            grupo=self.grupo, equipo1=self.e1, equipo2=self.e2,
        )

    def test_programar_el_horario_no_recalcula_la_tabla(self):
        from unittest.mock import patch

        from . import signals

        self.partido.fecha_hora = timezone.now() + timedelta(days=1)
        with patch.object(signals.EquipoGrupo.objects, 'bulk_update') as fake:
            self.partido.save(update_fields=['fecha_hora'])
        fake.assert_not_called()

    def test_marcar_recordatorio_no_recalcula_la_tabla(self):
        from unittest.mock import patch

        from . import signals

        self.partido.recordatorios_enviados = ['24h']
        with patch.object(signals.EquipoGrupo.objects, 'bulk_update') as fake:
            self.partido.save(update_fields=['recordatorios_enviados'])
        fake.assert_not_called()

    def test_guardar_un_resultado_si_recalcula(self):
        from unittest.mock import patch

        from . import signals

        self.partido.ganador = self.e1
        with patch.object(signals.EquipoGrupo.objects, 'bulk_update') as fake:
            self.partido.save()
        fake.assert_called()


class EngancheTelefonoTests(TestCase):
    """Auditoria - alto: el enganche por telefono agarraba cuentas ajenas.

    Comparaba los ULTIMOS 8 DIGITOS con endswith y devolvia el PRIMERO que
    matcheara, sin orden determinista. Dos numeros de ciudades distintas pueden
    coincidir en 8 digitos: se anotaba a un tercero a un torneo y se le
    mostraba su mail y telefono a quien estaba cargando el alta.
    """

    def setUp(self):
        self.division = Division.objects.create(nombre="Tercera", orden=5)

    def _jugador(self, email, telefono, **extra):
        return User.objects.create_user(
            email=email, password="x", nombre=email[:4], apellido="T",
            numero_telefono=telefono, division=self.division, **extra
        )

    def test_encuentra_el_mismo_numero_en_otro_formato(self):
        from .services.alta_sin_cuenta import buscar_jugador

        u = self._jugador("mar@test.com", "+54 9 223 593-7115")
        self.assertEqual(buscar_jugador(telefono="2235937115"), u)
        self.assertEqual(buscar_jugador(telefono="0223 15 593-7115"), u)

    def test_no_confunde_numeros_de_ciudades_distintas(self):
        from .services.alta_sin_cuenta import buscar_jugador

        # Mismos 8 digitos finales, caracteristica distinta: son dos personas.
        self._jugador("mardel@test.com", "+54 9 223 5937115")
        buscado = "+54 9 261 5937115"
        self.assertIsNone(
            buscar_jugador(telefono=buscado),
            "Engancho una cuenta ajena por coincidir solo los ultimos 8 digitos.",
        )

    def test_con_dos_candidatos_no_adivina(self):
        from .services.alta_sin_cuenta import buscar_jugador

        # Dos cuentas con el MISMO numero (duplicado real en la base).
        self._jugador("a@test.com", "2235937115")
        self._jugador("b@test.com", "+54 9 223 593 7115")
        self.assertIsNone(
            buscar_jugador(telefono="2235937115"),
            "Con dos candidatos hay que crear cuenta nueva, no elegir al azar.",
        )

    def test_ignora_numeros_demasiado_cortos(self):
        from .services.alta_sin_cuenta import buscar_jugador

        self._jugador("corto@test.com", "5937115")
        self.assertIsNone(buscar_jugador(telefono="5937115"))

    def test_no_resucita_una_cuenta_ya_fusionada(self):
        from .services.alta_sin_cuenta import buscar_jugador

        bueno = self._jugador("bueno@test.com", "2236337881")
        viejo = self._jugador("viejo@test.com", "2235937115")
        viejo.merged_into = bueno
        viejo.is_active = False
        viejo.save()

        self.assertIsNone(
            buscar_jugador(telefono="2235937115"),
            "Devolvio una cuenta que un admin ya habia fusionado.",
        )
        self.assertIsNone(buscar_jugador(email="viejo@test.com"))

    def test_el_email_sigue_teniendo_prioridad(self):
        from .services.alta_sin_cuenta import buscar_jugador

        u = self._jugador("Prio@Test.com", "2235937115")
        self.assertEqual(buscar_jugador(email="prio@test.com"), u)

    def test_inscripcion_directa_usa_el_mismo_criterio(self):
        from .services.inscripcion_directa import buscar_por_telefono

        u = self._jugador("dir@test.com", "+54 9 223 593-7115")
        self.assertEqual(buscar_por_telefono("2235937115"), u)
        self.assertIsNone(buscar_por_telefono("+54 9 261 5937115"))


class DesplegableParejasTests(TestCase):
    """Auditoria - alto: la gestion traia TODAS las parejas de la plataforma.

    Se acoto en SQL a las divisiones cercanas al torneo. El prefiltro es un
    superconjunto: la regla real la sigue aplicando es_division_permitida(),
    asi que la lista final tiene que ser identica a la de antes.
    """

    contador = 0

    def _equipo(self, div1, div2=None):
        DesplegableParejasTests.contador += 1
        n = DesplegableParejasTests.contador
        j1 = User.objects.create_user(
            email="dp%da@test.com" % n, password="x", nombre="D%dA" % n,
            apellido="X", division=div1,
        )
        j2 = User.objects.create_user(
            email="dp%db@test.com" % n, password="x", nombre="D%dB" % n,
            apellido="Y", division=div2 or div1,
        )
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=div1)

    def setUp(self):
        # Ocho divisiones, como en produccion.
        self.divs = {
            n: Division.objects.create(nombre="Div%d" % n, orden=n)
            for n in range(1, 9)
        }
        self.org = User.objects.create_user(
            email="org-dp@test.com", password="x", nombre="O", apellido="D",
            tipo_usuario="ADMIN", is_staff=True,
        )
        self.torneo = Torneo.objects.create(
            nombre="Quinta abierta", division=self.divs[5],
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO,
        )
        # Una pareja pura por division, mas una mixta ancha y una sin division.
        self.puras = {n: self._equipo(self.divs[n]) for n in range(1, 9)}
        self.mixta_ancha = self._equipo(self.divs[3], self.divs[7])
        self.sin_division = self._equipo(None, None)

    def _del_desplegable(self):
        self.client.force_login(self.org)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return {e.pk for e in resp.context["equipos_para_inscribir"]}

    def test_coincide_con_aplicar_la_regla_a_mano(self):
        from .views import es_division_permitida

        todos = list(Equipo.objects.filter(es_dummy=False, esta_activo=True))
        esperado = {
            eq.pk for eq in todos if es_division_permitida(eq, self.torneo)
        }
        self.assertEqual(
            self._del_desplegable(), esperado,
            "El prefiltro SQL cambio quien entra al desplegable.",
        )

    def test_entran_las_puras_de_mas_menos_una_division(self):
        obtenidos = self._del_desplegable()
        for n in (4, 5, 6):
            self.assertIn(self.puras[n].pk, obtenidos, "Falta la pura de Div%d" % n)

    def test_no_entran_las_puras_lejanas(self):
        obtenidos = self._del_desplegable()
        for n in (1, 2, 3, 7, 8):
            self.assertNotIn(self.puras[n].pk, obtenidos, "Entro la pura de Div%d" % n)

    def test_entra_la_mixta_que_abarca_la_division_del_torneo(self):
        # 3ra y 7ma abarcan de 3 a 7, o sea incluye la 5ta del torneo.
        self.assertIn(self.mixta_ancha.pk, self._del_desplegable())

    def test_entra_la_pareja_sin_division_cargada(self):
        self.assertIn(self.sin_division.pk, self._del_desplegable())


class ByesConCascadaTests(TestCase):
    """Un bye nace CON ganador. La cascada nueva no tiene que romperlo.

    `_resolver_byes` crea un Partido con ganador y resultado="Bye" para la
    pareja que pasa libre. Como ahora `Partido.save()` propaga (y puede
    invalidar) la ronda siguiente, hay que verificar que el flujo normal de un
    cuadro con byes sigue funcionando igual.
    """

    contador = 0

    def _equipo(self):
        ByesConCascadaTests.contador += 1
        n = ByesConCascadaTests.contador
        j1 = User.objects.create_user(email="by%da@t.com" % n, password="x",
                                      nombre="Y%dA" % n, apellido="X",
                                      division=self.division)
        j2 = User.objects.create_user(email="by%db@t.com" % n, password="x",
                                      nombre="Y%dB" % n, apellido="Y",
                                      division=self.division)
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)

    def setUp(self):
        self.division = Division.objects.create(nombre="ByeDiv", orden=6)
        self.torneo = Torneo.objects.create(
            nombre="Con byes", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=4, estado=Torneo.Estado.EN_JUEGO,
        )
        self.a, self.b, self.c = [self._equipo() for _ in range(3)]

    def test_el_bye_avanza_y_el_cuadro_queda_coherente(self):
        final = Partido.objects.create(torneo=self.torneo, ronda=2, orden_partido=1)
        # Semi 1: partido de verdad. Semi 2: bye (A pasa libre).
        semi1 = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.b, equipo2=self.c, siguiente_partido=final)
        semi2 = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=2,
            equipo1=self.a, siguiente_partido=final)

        # El bye se resuelve como lo hace la vista: ganador + resultado "Bye".
        semi2.ganador = self.a
        semi2.resultado = "Bye"
        semi2.save()

        final.refresh_from_db()
        self.assertEqual(final.equipo2_id, self.a.id, "El bye no avanzo a la final.")

        # Se juega la otra semi: el bye NO se tiene que tocar.
        semi1.ganador = self.b
        semi1.save()
        semi2.refresh_from_db()
        final.refresh_from_db()
        self.assertEqual(semi2.ganador_id, self.a.id, "La cascada borro el bye.")
        self.assertEqual(semi2.resultado, "Bye")
        self.assertEqual(final.equipo1_id, self.b.id)
        self.assertEqual(final.equipo2_id, self.a.id)

    def test_avanzar_clasificados_con_update_no_dispara_cascada(self):
        # "Avanzar clasificados" usa queryset.update(), que no llama a save():
        # los placeholders se llenan sin tocar resultados ya cargados.
        final = Partido.objects.create(torneo=self.torneo, ronda=2, orden_partido=1)
        semi = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            placeholder_e1="1A", placeholder_e2="2B", siguiente_partido=final)
        semi.ganador = None
        Partido.objects.filter(pk=semi.pk).update(equipo1=self.a, equipo2=self.b)
        semi.refresh_from_db()
        self.assertEqual(semi.equipo1_id, self.a.id)
        self.assertIsNone(semi.ganador_id)


class ImpactoDiagnosticoTests(TestCase):
    """La pagina de diagnostico muestra a que datos existentes los alcanzan
    los cambios de comportamiento. Sirve para revisar produccion sin shell."""

    def setUp(self):
        from accounts.models import Organizacion

        self.club = Organizacion.objects.create(nombre="Club Imp", alias="club-imp")
        self.admin = User.objects.create_user(
            email="admin-imp@test.com", password="x", nombre="A", apellido="I",
            tipo_usuario="ADMIN", is_staff=True)
        self.org = User.objects.create_user(
            email="org-imp@test.com", password="x", nombre="O", apellido="I",
            tipo_usuario="ORGANIZER", organizacion=self.club)
        self.url = reverse("torneos:revisar_torneos")

    def test_detecta_un_americano_sin_club(self):
        from .models import Americano
        from .services.impacto import revisar_impacto

        Americano.objects.create(nombre="Huerfano", tipo=Americano.Tipo.AMERICANO)
        imp = revisar_impacto()
        self.assertEqual(imp['americanos']['cantidad'], 1)
        self.assertTrue(imp['requiere_accion'])

    def test_sin_huerfanos_no_pide_accion(self):
        from .models import Americano
        from .services.impacto import revisar_impacto

        Americano.objects.create(nombre="Con club", tipo=Americano.Tipo.AMERICANO,
                                 organizacion=self.club)
        self.assertFalse(revisar_impacto()['requiere_accion'])

    def test_detecta_telefonos_cortos_y_compartidos(self):
        from .services.impacto import revisar_impacto

        User.objects.create_user(email="corto@t.com", password="x", nombre="C",
                                 apellido="T", numero_telefono="59371")
        User.objects.create_user(email="dup1@t.com", password="x", nombre="D1",
                                 apellido="T", numero_telefono="2235937115")
        User.objects.create_user(email="dup2@t.com", password="x", nombre="D2",
                                 apellido="T", numero_telefono="+54 9 223 593-7115")
        tel = revisar_impacto()['telefonos']
        self.assertEqual(tel['cantidad_cortos'], 1)
        self.assertEqual(tel['cantidad_compartidos'], 1)

    def test_solo_el_admin_ve_la_seccion(self):
        self.client.force_login(self.admin)
        self.assertIn('impacto', self.client.get(self.url).context)

        self.client.force_login(self.org)
        self.assertNotIn('impacto', self.client.get(self.url).context)


class DescribirEstructuraTests(TestCase):
    """TP-17.3: proyección de estructura para la vista previa del alta."""

    def test_grupos_con_formato_optimizado(self):
        # Zonas según la llave oficial FAP: n//3 zonas, las primeras n%3 de 4.
        from .formats import describir_estructura
        for n, num_zonas in [(6, 2), (8, 2), (12, 4), (13, 4), (16, 5), (17, 5), (24, 8), (26, 8), (48, 16)]:
            r = describir_estructura(n, 'G')
            self.assertTrue(r['ok'], f"n={n} debería ser ok")
            self.assertEqual(r['nivel'], 'ok')
            self.assertEqual(len(r['zonas']), num_zonas, f"n={n}")

    def test_grupos_sin_formato_optimizado_igual_genera(self):
        # Fuera del rango FAP (6-48) el sistema arma zonas genéricas igual.
        from .formats import describir_estructura
        for n in (5, 49, 60):
            r = describir_estructura(n, 'G')
            self.assertTrue(r['ok'], f"n={n}")
            self.assertEqual(r['nivel'], 'ok')
            self.assertTrue(r['zonas'])

    def test_llaves_fap_consistentes(self):
        # Invariantes de TODAS las llaves oficiales (6-48): cada clasificado se usa
        # exactamente una vez, cada partido recibe 2 entradas (seed o ganador),
        # hay una sola final y 1º y 2º de cada zona siempre clasifican.
        from .formats import FORMATS, fap_sizes, LETRAS
        self.assertEqual(sorted(FORMATS), list(range(6, 49)))
        for n, fmt in FORMATS.items():
            st = fmt.bracket_structure
            by_id = {m['id']: m for m in st}
            feeders, finals, seeds = {}, [], []
            for m in st:
                nx = m['next']
                if nx is None:
                    finals.append(m['id'])
                else:
                    self.assertIn(nx, by_id, f"n={n}: {m['id']}.next={nx} inexistente")
                    self.assertGreater(by_id[nx]['round'], m['round'], f"n={n}: ronda no crece en {m['id']}->{nx}")
                    feeders[nx] = feeders.get(nx, 0) + 1
                seeds += [t for t in (m['t1'], m['t2']) if t is not None]
            self.assertEqual(len(finals), 1, f"n={n}")
            # 2 entradas por partido
            for m in st:
                direct = len([t for t in (m['t1'], m['t2']) if t is not None])
                self.assertEqual(direct + feeders.get(m['id'], 0), 2, f"n={n} partido {m['id']}")
            self.assertEqual(len(seeds), len(st) + 1, f"n={n}: clasificados != partidos+1")
            self.assertEqual(len(seeds), len(set(seeds)), f"n={n}: clasificado repetido")
            sizes = fap_sizes(n)
            self.assertEqual(sum(sizes), n)
            by_zone = {}
            for (letra, pos) in seeds:
                by_zone.setdefault(letra, set()).add(pos)
            for i in range(len(sizes)):
                letra = LETRAS[i]
                self.assertIn(1, by_zone.get(letra, set()), f"n={n}: 1º de {letra} no clasifica")
                self.assertIn(2, by_zone.get(letra, set()), f"n={n}: 2º de {letra} no clasifica")
                self.assertLessEqual(max(by_zone[letra]), sizes[i], f"n={n}: zona {letra}")

    def test_grupos_pocas_parejas_avisa(self):
        from .formats import describir_estructura
        r = describir_estructura(3, 'G')
        self.assertFalse(r['ok'])
        self.assertEqual(r['nivel'], 'warn')

    def test_grupos_forzar_3_no_divisible_avisa(self):
        from .formats import describir_estructura
        r = describir_estructura(16, 'G', forzar3=True)
        self.assertEqual(r['nivel'], 'warn')
        r2 = describir_estructura(18, 'G', forzar3=True)
        self.assertEqual(r2['nivel'], 'ok')
        self.assertEqual(len(r2['zonas']), 6)
        self.assertTrue(all(z[1] == 3 for z in r2['zonas']))

    def test_eliminacion_directa_byes(self):
        from .formats import describir_estructura
        r = describir_estructura(13, 'E')
        self.assertTrue(r['ok'])
        self.assertEqual(r['byes'], 3)  # 16 - 13
        r2 = describir_estructura(16, 'E')
        self.assertEqual(r2['byes'], 0)
        r3 = describir_estructura(32, 'E')
        self.assertEqual(r3['byes'], 0)

    def test_eliminacion_directa_minimo(self):
        from .formats import describir_estructura
        r = describir_estructura(1, 'E')
        self.assertFalse(r['ok'])

    def test_estructura_grupos_coincide_con_generacion_real(self):
        # La proyección debe usar la MISMA función que la generación real.
        from .formats import describir_estructura, calcular_estructura_grupos
        for n in (6, 13, 16, 20, 24):
            _, sizes, _, _ = calcular_estructura_grupos(n)
            zonas = describir_estructura(n, 'G')['zonas']
            self.assertEqual([z[1] for z in zonas], sizes, f"n={n}")


@override_settings(STORAGES=TEST_STORAGES)
class TorneoAdminFormTests(TestCase):
    """TP-17.1/.4/.5: alta en secciones, prefijado desde org y validaciones."""

    def setUp(self):
        from accounts.models import Organizacion
        self.org = Organizacion.objects.create(
            nombre="AprendePadelMDQ", alias="aprendepadel",
            ciudad="Mar del Plata", direccion="Av. Constitución 5500",
        )
        self.organizador = User.objects.create_user(
            email="org@test.com", password="x", nombre="Orga", apellido="Test",
            tipo_usuario="ORGANIZER",
        )
        self.organizador.organizacion = self.org
        self.organizador.save()

    def _data(self, **over):
        data = {
            'nombre': 'Abierto Test', 'cupos_totales': 16,
            'equipos_por_grupo': 3, 'forzar_grupos_de_3': False,
            'formato_grupos_4': 'RR', 'tipo_torneo': 'G', 'categoria': 'X',
            'fecha_limite_inscripcion': '2030-01-01T10:00',
            'fecha_inicio': '2030-01-05',
        }
        data.update(over)
        return data

    def test_foto_campeones_ausente_al_crear(self):
        from .forms import TorneoAdminForm
        form = TorneoAdminForm()
        self.assertNotIn('foto_campeones', form.fields)

    def test_foto_campeones_presente_al_editar(self):
        from .forms import TorneoAdminForm
        t = Torneo.objects.create(
            nombre="T", fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
        )
        form = TorneoAdminForm(instance=t)
        self.assertIn('foto_campeones', form.fields)

    def test_prefijar_sede_desde_organizacion(self):
        from .forms import TorneoAdminForm
        form = TorneoAdminForm(user=self.organizador)
        self.assertEqual(form.initial.get('sede_nombre'), "AprendePadelMDQ")
        self.assertEqual(form.initial.get('ciudad'), "Mar del Plata")
        self.assertEqual(form.initial.get('sede_direccion'), "Av. Constitución 5500")

    def test_form_valido(self):
        from .forms import TorneoAdminForm
        form = TorneoAdminForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_cierre_despues_del_inicio_bloquea(self):
        from .forms import TorneoAdminForm
        form = TorneoAdminForm(data=self._data(
            fecha_limite_inscripcion='2030-01-10T10:00', fecha_inicio='2030-01-05'))
        self.assertFalse(form.is_valid())
        self.assertIn('fecha_limite_inscripcion', form.errors)

    def test_cupos_insuficientes_grupos_bloquea(self):
        from .forms import TorneoAdminForm
        form = TorneoAdminForm(data=self._data(cupos_totales=2, tipo_torneo='G'))
        self.assertFalse(form.is_valid())
        self.assertIn('cupos_totales', form.errors)

    def test_cupos_bajos_eliminacion_no_bloquea(self):
        from .forms import TorneoAdminForm
        form = TorneoAdminForm(data=self._data(cupos_totales=2, tipo_torneo='E'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_render_alta_secciones_y_preview(self):
        self.client.force_login(self.organizador)
        r = self.client.get(reverse('torneos:admin_crear'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for needle in ['Lo básico', 'Cuándo y cuántos', 'id="preview-estructura"',
                       'Opciones avanzadas', 'Usar los datos de mi organización',
                       'admin/preview-estructura']:
            self.assertIn(needle, html)
        # La foto de campeones NO se pide al crear.
        self.assertNotIn('id_foto_campeones', html)

    def test_endpoint_preview_estructura(self):
        self.client.force_login(self.organizador)
        r = self.client.get(reverse('torneos:admin_preview_estructura'),
                             {'n': 16, 'tipo': 'G'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['nivel'], 'ok')
        self.assertEqual(len(data['zonas']), 5)


@override_settings(STORAGES=TEST_STORAGES)
class WalkoverAbandonoTests(TestCase):
    """TP-18: Walkover y Abandono al cargar resultados."""

    _c = 0

    def _equipo(self, division):
        WalkoverAbandonoTests._c += 1
        n = WalkoverAbandonoTests._c
        j1 = User.objects.create_user(email=f"wo{n}a@t.com", password="x",
                                      nombre=f"N{n}A", apellido=f"A{n}A", division=division)
        j2 = User.objects.create_user(email=f"wo{n}b@t.com", password="x",
                                      nombre=f"N{n}B", apellido=f"A{n}B", division=division)
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=division)

    def setUp(self):
        self.division = Division.objects.create(nombre="Quinta", orden=5)
        self.torneo = Torneo.objects.create(
            nombre="WO Test", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=6, estado=Torneo.Estado.EN_JUEGO,
        )
        self.grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        self.e1 = self._equipo(self.division)
        self.e2 = self._equipo(self.division)
        EquipoGrupo.objects.create(grupo=self.grupo, equipo=self.e1, numero=1)
        EquipoGrupo.objects.create(grupo=self.grupo, equipo=self.e2, numero=2)
        self.partido = PartidoGrupo.objects.create(
            grupo=self.grupo, equipo1=self.e1, equipo2=self.e2)

    def test_grupo_walkover_convencion_tabla(self):
        from .forms import CargarResultadoGrupoForm
        form = CargarResultadoGrupoForm(
            data={'resolucion': 'W', 'lado_ganador': '1'}, instance=self.partido)
        self.assertTrue(form.is_valid(), form.errors)
        p = form.save()
        self.assertEqual(p.ganador, self.e1)
        self.assertEqual(p.resultado, "W.O.")
        self.assertEqual((p.e1_sets_ganados, p.e2_sets_ganados), (2, 0))
        self.assertEqual((p.e1_games_ganados, p.e2_games_ganados), (0, 0))
        # Tabla (la recalcula el signal al guardar): W.O. = 2-0 en sets, sin games.
        eg1 = EquipoGrupo.objects.get(grupo=self.grupo, equipo=self.e1)
        eg2 = EquipoGrupo.objects.get(grupo=self.grupo, equipo=self.e2)
        self.assertEqual((eg1.partidos_ganados, eg1.diferencia_sets, eg1.games_a_favor), (1, 2, 0))
        self.assertEqual((eg2.partidos_perdidos, eg2.diferencia_sets, eg2.games_a_favor), (1, -2, 0))

    def test_grupo_abandono_gana_el_que_sigue(self):
        from .forms import CargarResultadoGrupoForm
        # El equipo1 iba ganando 6-2 pero abandona -> gana el equipo2.
        form = CargarResultadoGrupoForm(
            data={'resolucion': 'A', 'lado_abandona': '1',
                  'e1_set1': 6, 'e2_set1': 2}, instance=self.partido)
        self.assertTrue(form.is_valid(), form.errors)
        p = form.save()
        self.assertEqual(p.ganador, self.e2)
        self.assertIn("abandono", p.resultado)
        # Los games del parcial se cuentan como un partido normal.
        self.assertEqual((p.e1_games_ganados, p.e2_games_ganados), (6, 2))
        eg2 = EquipoGrupo.objects.get(grupo=self.grupo, equipo=self.e2)
        self.assertEqual(eg2.partidos_ganados, 1)

    def test_grupo_walkover_requiere_ganador(self):
        from .forms import CargarResultadoGrupoForm
        form = CargarResultadoGrupoForm(data={'resolucion': 'W'}, instance=self.partido)
        self.assertFalse(form.is_valid())
        self.assertIn('lado_ganador', form.errors)

    def test_bracket_walkover_avanza(self):
        from .forms import PartidoResultadoForm
        final = Partido.objects.create(torneo=self.torneo, ronda=2, orden_partido=1)
        semi = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.e1, equipo2=self.e2, siguiente_partido=final)
        form = PartidoResultadoForm(
            data={'resolucion': 'W', 'lado_ganador': '1'}, instance=semi)
        self.assertTrue(form.is_valid(), form.errors)
        p = form.save()
        self.assertEqual(p.ganador, self.e1)
        self.assertEqual(p.resultado, "W.O.")
        final.refresh_from_db()
        self.assertEqual(final.equipo1, self.e1)  # avanzó al siguiente partido

    def test_bracket_abandono_gana_el_que_sigue(self):
        from .forms import PartidoResultadoForm
        partido = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.e1, equipo2=self.e2)
        form = PartidoResultadoForm(
            data={'resolucion': 'A', 'lado_abandona': '2',
                  'set1_local': 6, 'set1_visitante': 4}, instance=partido)
        self.assertTrue(form.is_valid(), form.errors)
        p = form.save()
        self.assertEqual(p.ganador, self.e1)
        self.assertIn("abandono", p.resultado)


@override_settings(STORAGES=TEST_STORAGES)
class PlacaRedesTests(TestCase):
    """TP-placas: kit de placas 9:16 para redes."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Quinta", orden=5)
        self.torneo = Torneo.objects.create(
            nombre="Abierto Placa", division=self.division, categoria='X',
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO,
            sede_nombre="Club Test", ciudad="Mar del Plata", premio="Trofeos")

    def _eq(self):
        c = getattr(self, '_c', 0) + 1
        self._c = c
        j1 = User.objects.create_user(email=f"pl{c}a@t.com", password="x", nombre="Gabi", apellido="Tesoriere", division=self.division)
        j2 = User.objects.create_user(email=f"pl{c}b@t.com", password="x", nombre="Marta", apellido="Lopez", division=self.division)
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)

    def test_placa_app_generica(self):
        html = self.client.get(reverse('torneos:placa_app')).content.decode()
        self.assertIn("Tu pádel", html)
        self.assertIn("js/placa.js", html)
        self.assertIn("html2canvas", html)

    def test_placa_anuncio(self):
        url = reverse('torneos:placa', kwargs={'pk': self.torneo.pk}) + '?tipo=anuncio'
        html = self.client.get(url).content.decode()
        self.assertIn("Inscripción abierta", html)
        self.assertIn("Abierto Placa", html)
        self.assertIn("¡Quedan pocos cupos!", html)

    def test_placa_default_por_estado(self):
        # Torneo ABIERTO sin ?tipo -> anuncio
        html = self.client.get(reverse('torneos:placa', kwargs={'pk': self.torneo.pk})).content.decode()
        self.assertIn("Inscripción abierta", html)

    def test_placa_campeones(self):
        eq = self._eq()
        self.torneo.estado = Torneo.Estado.FINALIZADO
        self.torneo.ganador_del_torneo = eq
        self.torneo.save()
        Partido.objects.create(
            torneo=self.torneo, ronda=2, orden_partido=1,
            equipo1=eq, equipo2=self._eq(), ganador=eq, resultado="6-3 6-4")
        url = reverse('torneos:placa', kwargs={'pk': self.torneo.pk}) + '?tipo=campeones'
        html = self.client.get(url).content.decode()
        self.assertIn("Campeones", html)
        self.assertIn("6-3 6-4", html)
        self.assertIn("Tesoriere", html)


@override_settings(STORAGES=TEST_STORAGES)
class PushEventosTests(TestCase):
    """TP-11: eventos de push adicionales (resultado, programado)."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Once", orden=11)
        self.torneo = Torneo.objects.create(
            nombre="Push Cup", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            estado=Torneo.Estado.EN_JUEGO)
        self.grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        js = []
        for i in range(4):
            js.append(User.objects.create_user(
                email=f"pe{i}@t.com", password="x", nombre=f"J{i}", apellido="Push",
                division=self.division))
        self.e1 = Equipo.objects.create(jugador1=js[0], jugador2=js[1], division=self.division)
        self.e2 = Equipo.objects.create(jugador1=js[2], jugador2=js[3], division=self.division)

    def test_push_resultado_notifica_a_ambos_equipos(self):
        from unittest.mock import patch
        from torneos.views import _push_resultado
        p = PartidoGrupo.objects.create(
            grupo=self.grupo, equipo1=self.e1, equipo2=self.e2,
            e1_set1=6, e2_set1=3, e1_sets_ganados=2, e2_sets_ganados=0, ganador=self.e1)
        with patch('accounts.push.send_push_to_users') as m:
            _push_resultado(p, self.torneo)
        m.assert_called_once()
        users = m.call_args.args[0]
        self.assertEqual(len(users), 4)
        self.assertEqual(m.call_args.kwargs['title'], "📊 Resultado cargado")

    def test_push_programado_notifica(self):
        from unittest.mock import patch
        from torneos.views import _push_programado
        p = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.e1, equipo2=self.e2, fecha_hora=timezone.now())
        with patch('accounts.push.send_push_to_users') as m:
            _push_programado(p, self.torneo)
        m.assert_called_once()
        self.assertIn("Partido programado", m.call_args.kwargs['title'])

    def test_sin_ganador_no_notifica(self):
        from unittest.mock import patch
        from torneos.views import _push_resultado
        p = PartidoGrupo.objects.create(grupo=self.grupo, equipo1=self.e1, equipo2=self.e2)
        with patch('accounts.push.send_push_to_users') as m:
            _push_resultado(p, self.torneo)
        m.assert_not_called()


@override_settings(STORAGES=TEST_STORAGES)
class ElegibilidadNotificacionesTests(TestCase):
    """Filtros de 'compatibilidad' para notificar un torneo nuevo (email + push)."""

    def setUp(self):
        self.septima = Division.objects.create(nombre="Séptima", orden=7)
        self.sexta = Division.objects.create(nombre="Sexta", orden=6)
        self.octava = Division.objects.create(nombre="Octava", orden=8)
        self.cuarta = Division.objects.create(nombre="Cuarta", orden=4)
        self.torneo = Torneo.objects.create(
            nombre="Abierto MDQ", division=self.septima, categoria='F',
            ciudad="Mar del Plata",
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=3))

    def _j(self, email, division, genero='FEMENINO', ciudad='', dummy=False):
        return User.objects.create_user(
            email=email, password="x", nombre="N", apellido="A",
            genero=genero, division=division, ciudad=ciudad, is_dummy=dummy)

    def test_filtros_completos(self):
        from torneos.emails import jugadores_elegibles_para_torneo
        ok_misma_div = self._j("a@t.com", self.septima, ciudad="Mar del Plata")
        ok_div_arriba = self._j("b@t.com", self.sexta, ciudad="mar del plata")  # normaliza mayúsculas
        ok_div_abajo = self._j("c@t.com", self.octava)                          # sin ciudad -> recibe igual
        no_div_lejana = self._j("d@t.com", self.cuarta)                         # división muy lejos
        no_genero = self._j("e@t.com", self.septima, genero='MASCULINO')        # torneo femenino
        no_otra_ciudad = self._j("f@t.com", self.septima, ciudad="Córdoba")     # otra ciudad
        no_dummy = self._j("g@t.com", self.septima, dummy=True)                 # dummy

        ids = {j.id for j in jugadores_elegibles_para_torneo(self.torneo)}
        self.assertIn(ok_misma_div.id, ids)
        self.assertIn(ok_div_arriba.id, ids)
        self.assertIn(ok_div_abajo.id, ids)
        self.assertNotIn(no_div_lejana.id, ids)
        self.assertNotIn(no_genero.id, ids)
        self.assertNotIn(no_otra_ciudad.id, ids)
        self.assertNotIn(no_dummy.id, ids)

    def test_ciudad_con_tildes_matchea(self):
        from torneos.emails import jugadores_elegibles_para_torneo
        self.torneo.ciudad = "Córdoba"
        self.torneo.save()
        j = self._j("h@t.com", self.septima, ciudad="cordoba")  # sin tilde
        ids = {x.id for x in jugadores_elegibles_para_torneo(self.torneo)}
        self.assertIn(j.id, ids)

    def test_torneo_sin_ciudad_no_filtra(self):
        from torneos.emails import jugadores_elegibles_para_torneo
        self.torneo.ciudad = ""
        self.torneo.save()
        j = self._j("i@t.com", self.septima, ciudad="Córdoba")
        ids = {x.id for x in jugadores_elegibles_para_torneo(self.torneo)}
        self.assertIn(j.id, ids)


@override_settings(STORAGES=TEST_STORAGES)
class AgregarZonaTests(TestCase):
    """Agregar una zona nueva con parejas a un torneo ya iniciado, sin tocar lo existente."""

    _c = 0

    def _equipo(self, division):
        AgregarZonaTests._c += 1
        n = AgregarZonaTests._c
        j1 = User.objects.create_user(email=f"az{n}a@t.com", password="x",
                                      nombre=f"N{n}A", apellido=f"A{n}A", division=division)
        j2 = User.objects.create_user(email=f"az{n}b@t.com", password="x",
                                      nombre=f"N{n}B", apellido=f"A{n}B", division=division)
        return Equipo.objects.create(jugador1=j1, jugador2=j2, division=division)

    def setUp(self):
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.admin = User.objects.create_user(
            email="adminaz@t.com", password="x", nombre="Adm", apellido="In",
            tipo_usuario="ADMIN", is_staff=True)
        self.torneo = Torneo.objects.create(
            nombre="Torneo 12", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=12, estado=Torneo.Estado.EN_JUEGO)
        # 4 zonas de 3, ya generadas, con un resultado cargado en la Zona A
        self.zonas = []
        idx = 0
        letras = 'ABCD'
        for L in letras:
            g = Grupo.objects.create(torneo=self.torneo, nombre=f"Zona {L}")
            eqs = [self._equipo(self.division) for _ in range(3)]
            for n, eq in enumerate(eqs, 1):
                Inscripcion.objects.create(torneo=self.torneo, equipo=eq)
                EquipoGrupo.objects.create(grupo=g, equipo=eq, numero=n)
            from torneos.views import generar_partidos_grupos
            generar_partidos_grupos(self.torneo, eqs, g)
            self.zonas.append((g, eqs))
        # Cargar un resultado en la zona A (para verificar que NO se pierde)
        za, eqa = self.zonas[0]
        pg = za.partidos_grupo.first()
        pg.e1_set1, pg.e2_set1, pg.e1_sets_ganados, pg.e2_sets_ganados = 6, 2, 2, 0
        pg.ganador = pg.equipo1
        pg.save()
        self.partidos_antes = PartidoGrupo.objects.filter(grupo__torneo=self.torneo).count()

    def test_agregar_zona_crea_grupo_y_partidos(self):
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        self.client.post(url, {"action": "agregar_zona",
                               "nombres_parejas": "Bigoni/Sanchez\nPerez/Lopez"})
        # Zona nueva creada (la 5ta -> "Zona E")
        self.torneo.refresh_from_db()
        self.assertEqual(self.torneo.grupos.count(), 5)
        nueva = self.torneo.grupos.get(nombre="Zona E")
        self.assertEqual(nueva.tabla.count(), 2)
        # Round robin de 2 parejas = 1 partido nuevo, sin tocar los previos
        self.assertEqual(nueva.partidos_grupo.count(), 1)
        self.assertEqual(PartidoGrupo.objects.filter(grupo__torneo=self.torneo).count(),
                         self.partidos_antes + 1)
        # Flag de estructura manual
        self.assertTrue(self.torneo.estructura_manual)
        # El resultado previo de la Zona A sigue intacto
        za = self.torneo.grupos.get(nombre="Zona A")
        self.assertTrue(za.partidos_grupo.filter(ganador__isnull=False).exists())

    def test_menos_de_2_parejas_falla(self):
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        self.client.post(url, {"action": "agregar_zona", "nombres_parejas": "Solo Una"})
        self.torneo.refresh_from_db()
        self.assertEqual(self.torneo.grupos.count(), 4)  # no se creó zona

    def test_bracket_incluye_zona_manual(self):
        # Cerrar todas las zonas y agregar una zona manual -> el bracket genérico
        # debe contemplar las 5 zonas (10 clasificados -> cuadro de 16).
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        self.client.post(url, {"action": "agregar_zona",
                               "nombres_parejas": "Bigoni/Sanchez\nPerez/Lopez"})
        # Cerrar TODOS los partidos de grupo (ganador = equipo1)
        for pg in PartidoGrupo.objects.filter(grupo__torneo=self.torneo, ganador__isnull=True):
            pg.e1_sets_ganados, pg.e2_sets_ganados = 2, 0
            pg.ganador = pg.equipo1
            pg.save()
        self.client.post(url, {"action": "generar_octavos"})
        from torneos.models import Partido
        # 10 clasificados -> bracket de 16 -> 4 rondas (octavos..final)
        rondas = set(Partido.objects.filter(torneo=self.torneo).values_list('ronda', flat=True))
        self.assertTrue(Partido.objects.filter(torneo=self.torneo).exists())
        self.assertGreaterEqual(len(rondas), 3)
        # Las parejas de la zona nueva (1ro y 2do) deben aparecer en el cuadro.
        zona_e = self.torneo.grupos.get(nombre="Zona E")
        ids_zona_e = set(zona_e.tabla.values_list('equipo_id', flat=True))
        ids_en_cuadro = set()
        for p in Partido.objects.filter(torneo=self.torneo):
            if p.equipo1_id:
                ids_en_cuadro.add(p.equipo1_id)
            if p.equipo2_id:
                ids_en_cuadro.add(p.equipo2_id)
        self.assertTrue(ids_zona_e & ids_en_cuadro,
                        "Las parejas de la zona nueva deben clasificar al cuadro")

    def test_play_in_octavos_solo_dos_cruces(self):
        # 5 zonas (14 eq) cerradas -> 10 clasificados -> cuadro 16 con play-in:
        # la 1ra ronda (octavos) tiene SOLO 2 cruces; el resto arranca en cuartos.
        from torneos.models import Partido
        from django.db.models import Min
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        self.client.post(url, {"action": "agregar_zona",
                               "nombres_parejas": "Bigoni/Sanchez\nPerez/Lopez"})
        for pg in PartidoGrupo.objects.filter(grupo__torneo=self.torneo, ganador__isnull=True):
            pg.e1_sets_ganados, pg.e2_sets_ganados = 2, 0
            pg.ganador = pg.equipo1
            pg.save()
        self.client.post(url, {"action": "generar_octavos"})
        min_ronda = Partido.objects.filter(torneo=self.torneo).aggregate(Min("ronda"))["ronda__min"]
        octavos = Partido.objects.filter(torneo=self.torneo, ronda=min_ronda)
        self.assertEqual(octavos.count(), 2, "octavos debe tener solo 2 cruces (play-in)")
        for o in octavos:
            self.assertIsNotNone(o.equipo1_id)
            self.assertIsNotNone(o.equipo2_id)
        # Cuartos: 4 partidos, con las 6 parejas directas ya colocadas
        cuartos = Partido.objects.filter(torneo=self.torneo, ronda=min_ronda + 1)
        self.assertEqual(cuartos.count(), 4)

    def test_octavos_son_solo_segundos(self):
        # Criterio: los PRIMEROS de zona pasan directo; los octavos los juegan los
        # SEGUNDOS. En el cuadro vacio, los placeholders de octavos deben ser todos 2X.
        from torneos.models import Partido
        from django.db.models import Min
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        self.client.post(url, {"action": "agregar_zona",
                               "nombres_parejas": "Bigoni/Sanchez\nPerez/Lopez"})
        self.client.post(url, {"action": "forzar_cuadro_vacio"})
        min_ronda = Partido.objects.filter(torneo=self.torneo).aggregate(Min("ronda"))["ronda__min"]
        octavos = Partido.objects.filter(torneo=self.torneo, ronda=min_ronda)
        self.assertEqual(octavos.count(), 2)
        for o in octavos:
            for ph in (o.placeholder_e1, o.placeholder_e2):
                self.assertTrue(ph and ph.startswith("2"),
                                f"octavos deben ser solo segundos, vino {ph}")
        # Los 5 primeros (1A-1E) arrancan directo en cuartos
        cuartos = Partido.objects.filter(torneo=self.torneo, ronda=min_ronda + 1)
        phs = []
        for c in cuartos:
            phs += [c.placeholder_e1, c.placeholder_e2]
        primeros = [p for p in phs if p and p.startswith("1")]
        self.assertEqual(len(primeros), 5)

    def test_cuadro_vacio_sin_cruces_fantasma(self):
        # 5 zonas (14 equipos) -> cuadro de 16 con byes intercalados, sin (vacio vs vacio).
        from torneos.models import Partido
        from django.db.models import Min
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        self.client.post(url, {"action": "agregar_zona",
                               "nombres_parejas": "Bigoni/Sanchez\nPerez/Lopez"})
        self.client.post(url, {"action": "forzar_cuadro_vacio"})
        min_ronda = Partido.objects.filter(torneo=self.torneo).aggregate(Min("ronda"))["ronda__min"]
        for p in Partido.objects.filter(torneo=self.torneo, ronda=min_ronda):
            vacio = (not p.equipo1_id and not p.placeholder_e1
                     and not p.equipo2_id and not p.placeholder_e2)
            self.assertFalse(vacio, "no debe haber cruces totalmente vacios en el cuadro")

    def test_agregar_zona_resetea_llave_existente(self):
        from torneos.models import Partido
        self.client.force_login(self.admin)
        url = reverse("torneos:admin_manage", kwargs={"pk": self.torneo.pk})
        # Cerrar las 4 zonas y armar la llave (formato de 12)
        for pg in PartidoGrupo.objects.filter(grupo__torneo=self.torneo, ganador__isnull=True):
            pg.e1_sets_ganados, pg.e2_sets_ganados = 2, 0
            pg.ganador = pg.equipo1
            pg.save()
        self.client.post(url, {"action": "generar_octavos"})
        self.assertTrue(Partido.objects.filter(torneo=self.torneo).exists())
        # Agregar zona -> la llave obsoleta se borra automáticamente
        self.client.post(url, {"action": "agregar_zona",
                               "nombres_parejas": "Bigoni/Sanchez\nPerez/Lopez"})
        self.assertFalse(Partido.objects.filter(torneo=self.torneo).exists())


class SeedConByesTests(TestCase):
    """El cuadro genérico distribuye los byes sin enfrentar dos byes (sin cruces fantasma)."""

    def test_distribucion_sin_pares_vacios(self):
        from torneos.views import _seed_con_byes
        for n, bs in [(10, 16), (6, 8), (12, 16), (8, 8), (5, 8), (3, 4), (9, 16)]:
            slots = _seed_con_byes(list(range(n)), bs)
            self.assertEqual(len(slots), bs)
            for i in range(0, bs, 2):
                self.assertFalse(slots[i] is None and slots[i + 1] is None,
                                 f"par vacío con n={n}, bs={bs}")
            self.assertEqual(sorted(x for x in slots if x is not None), list(range(n)))


@override_settings(STORAGES=TEST_STORAGES)
class FormatoPersonalizadoTests(TestCase):
    """Creador de formatos: guardar estructura de zonas y usarla al iniciar el torneo."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgFmt", alias="orgfmt")
        self.org_user = User.objects.create_user(
            email="orgf@t.com", password="x", nombre="Org", apellido="F",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.org_user.organizacion = self.org
        self.org_user.save()

    def test_form_parsea_sizes(self):
        from torneos.forms import FormatoPersonalizadoForm
        f = FormatoPersonalizadoForm(data={"nombre": "Liga 14", "sizes_texto": "3,3,3,3,2", "clasifican_por_grupo": 2})
        self.assertTrue(f.is_valid(), f.errors)
        obj = f.save(commit=False)
        obj.organizacion = self.org
        obj.save()
        self.assertEqual(obj.sizes, [3, 3, 3, 3, 2])
        self.assertEqual(obj.num_grupos, 5)
        self.assertEqual(obj.total_parejas, 14)

    def test_form_rechaza_grupo_de_uno_y_un_solo_grupo(self):
        from torneos.forms import FormatoPersonalizadoForm
        self.assertFalse(FormatoPersonalizadoForm(
            data={"nombre": "x", "sizes_texto": "3,1", "clasifican_por_grupo": 2}).is_valid())
        self.assertFalse(FormatoPersonalizadoForm(
            data={"nombre": "x", "sizes_texto": "4", "clasifican_por_grupo": 2}).is_valid())

    def test_iniciar_torneo_con_formato_crea_esas_zonas(self):
        from torneos.models import FormatoPersonalizado
        fmt = FormatoPersonalizado.objects.create(
            nombre="3+3+2", organizacion=self.org, sizes=[3, 3, 2], clasifican_por_grupo=2)
        torneo = Torneo.objects.create(
            nombre="Con Formato", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.ABIERTO,
            formato_personalizado=fmt)
        # 8 inscriptos
        for i in range(8):
            j1 = User.objects.create_user(email=f"f{i}a@t.com", password="x", nombre=f"J{i}", apellido="A", division=self.division)
            j2 = User.objects.create_user(email=f"f{i}b@t.com", password="x", nombre=f"K{i}", apellido="B", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=torneo, equipo=eq)
        self.client.force_login(self.org_user)
        url = reverse("torneos:admin_manage", kwargs={"pk": torneo.pk})
        self.client.post(url, {"action": "iniciar_torneo"})
        torneo.refresh_from_db()
        self.assertEqual(torneo.grupos.count(), 3)            # 3 zonas del formato
        self.assertTrue(torneo.estructura_manual)             # llave usa la genérica
        self.assertEqual(torneo.estado, Torneo.Estado.EN_JUEGO)

    def test_lista_formatos_accesible(self):
        self.client.force_login(self.org_user)
        r = self.client.get(reverse("torneos:formatos_list"))
        self.assertEqual(r.status_code, 200)

    def test_clasifican_uno_cuadro_solo_primeros(self):
        # Formato con "pasa 1 por zona": el cuadro vacío debe tener solo labels 1X.
        from torneos.models import FormatoPersonalizado, Partido
        fmt = FormatoPersonalizado.objects.create(
            nombre="1x5", organizacion=self.org, sizes=[3, 3, 3, 3, 3], clasifican_por_grupo=1)
        torneo = Torneo.objects.create(
            nombre="Pasa Uno", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=15, estado=Torneo.Estado.ABIERTO, formato_personalizado=fmt)
        for i in range(15):
            j1 = User.objects.create_user(email=f"u1{i}@t.com", password="x", nombre=f"P{i}", apellido="A", division=self.division)
            j2 = User.objects.create_user(email=f"u2{i}@t.com", password="x", nombre=f"Q{i}", apellido="B", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=torneo, equipo=eq)
        self.client.force_login(self.org_user)
        url = reverse("torneos:admin_manage", kwargs={"pk": torneo.pk})
        self.client.post(url, {"action": "iniciar_torneo"})
        labels = []
        for p in Partido.objects.filter(torneo=torneo):
            labels += [x for x in (p.placeholder_e1, p.placeholder_e2) if x]
        self.assertTrue(labels)
        self.assertTrue(all(x.startswith("1") for x in labels),
                        f"con clasifican=1 solo deben aparecer primeros: {labels}")

    def test_editor_render_interactivo(self):
        self.client.force_login(self.org_user)
        html = self.client.get(reverse("torneos:formato_crear")).content.decode()
        self.assertIn("Agregar zona", html)
        self.assertIn('id="zonas-list"', html)
        self.assertIn('id="sizes_texto"', html)
        self.assertIn("Así queda", html)

    def test_alta_torneo_ofrece_solo_formatos_de_la_org(self):
        from accounts.models import Organizacion
        from torneos.models import FormatoPersonalizado
        from torneos.forms import TorneoAdminForm
        otra = Organizacion.objects.create(nombre="Otra", alias="otra")
        mio = FormatoPersonalizado.objects.create(nombre="Mío", organizacion=self.org, sizes=[3, 3])
        ajeno = FormatoPersonalizado.objects.create(nombre="Ajeno", organizacion=otra, sizes=[3, 3])
        form = TorneoAdminForm(user=self.org_user)
        qs = form.fields['formato_personalizado'].queryset
        self.assertIn(mio, qs)
        self.assertNotIn(ajeno, qs)


@override_settings(STORAGES=TEST_STORAGES)
class CrucesManualesTests(TestCase):
    """Editor de cruces manuales de la fase final."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Quinta", orden=5)
        self.org = Organizacion.objects.create(nombre="OrgCM", alias="orgcm")
        self.org_user = User.objects.create_user(
            email="ocm@t.com", password="x", nombre="O", apellido="C",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.org_user.organizacion = self.org
        self.org_user.save()

    def test_form_page_incluye_preview_bracket(self):
        # La página del editor renderiza sin errores e incluye la vista previa del cuadro.
        self.client.force_login(self.org_user)
        resp = self.client.get(reverse("torneos:formato_crear"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="bracket-preview"', html)
        self.assertIn('renderBracket', html)

    def test_form_cruces_validos_se_guardan(self):
        import json
        from torneos.forms import FormatoPersonalizadoForm
        data = {"nombre": "M4", "sizes_texto": "3,3", "clasifican_por_grupo": 2,
                "cruces_json": json.dumps([["1A", "2B"], ["1B", "2A"]])}
        f = FormatoPersonalizadoForm(data=data)
        self.assertTrue(f.is_valid(), f.errors)
        obj = f.save(commit=False); obj.organizacion = self.org; obj.save()
        self.assertEqual(len(obj.cruces_manuales), 2)

    def test_form_cruces_repetido_invalido(self):
        import json
        from torneos.forms import FormatoPersonalizadoForm
        data = {"nombre": "M", "sizes_texto": "3,3", "clasifican_por_grupo": 2,
                "cruces_json": json.dumps([["1A", "2B"], ["1A", "2A"]])}
        self.assertFalse(FormatoPersonalizadoForm(data=data).is_valid())

    def test_form_cruces_incompletos_invalido(self):
        import json
        from torneos.forms import FormatoPersonalizadoForm
        # solo 1 cruce -> no cubre los 4 clasificados
        data = {"nombre": "M", "sizes_texto": "3,3", "clasifican_por_grupo": 2,
                "cruces_json": json.dumps([["1A", "2B"]])}
        self.assertFalse(FormatoPersonalizadoForm(data=data).is_valid())

    def test_form_cruces_con_byes_validos(self):
        # 5 zonas x 2 = 10 clasificados -> cuadro de 16 -> 8 posiciones (2 partidos + 6 byes)
        import json
        from torneos.forms import FormatoPersonalizadoForm
        cruces = [["1A", "2B"], ["1C", ""], ["1D", ""], ["1E", ""],
                  ["2A", ""], ["2C", ""], ["2D", "2E"], ["1B", ""]]
        data = {"nombre": "M10", "sizes_texto": "2,2,2,2,2", "clasifican_por_grupo": 2,
                "cruces_json": json.dumps(cruces)}
        f = FormatoPersonalizadoForm(data=data)
        self.assertTrue(f.is_valid(), f.errors)
        obj = f.save(commit=False); obj.organizacion = self.org; obj.save()
        self.assertEqual(len(obj.cruces_manuales), 8)

    def test_form_cruces_byes_posiciones_incorrectas(self):
        # 10 clasificados requieren 8 posiciones; definir 4 -> inválido
        import json
        from torneos.forms import FormatoPersonalizadoForm
        cruces = [["1A", "2B"], ["1C", "2D"], ["1E", "2A"], ["1B", "2C"]]
        data = {"nombre": "M", "sizes_texto": "2,2,2,2,2", "clasifican_por_grupo": 2,
                "cruces_json": json.dumps(cruces)}
        self.assertFalse(FormatoPersonalizadoForm(data=data).is_valid())

    def test_generacion_con_byes(self):
        from torneos.models import FormatoPersonalizado, Partido
        from django.db.models import Min
        cruces = [["1A", "2B"], ["1C", ""], ["1D", ""], ["1E", ""],
                  ["2A", ""], ["2C", ""], ["2D", "2E"], ["1B", ""]]
        fmt = FormatoPersonalizado.objects.create(
            nombre="Manual10", organizacion=self.org, sizes=[2, 2, 2, 2, 2],
            clasifican_por_grupo=2, cruces_manuales=cruces)
        torneo = Torneo.objects.create(
            nombre="Con Byes", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=20, estado=Torneo.Estado.ABIERTO, formato_personalizado=fmt)
        for i in range(10):
            j1 = User.objects.create_user(email=f"by{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"by{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=torneo, equipo=eq)
        self.client.force_login(self.org_user)
        url = reverse("torneos:admin_manage", kwargs={"pk": torneo.pk})
        self.client.post(url, {"action": "iniciar_torneo"})
        min_ronda = Partido.objects.filter(torneo=torneo).aggregate(Min("ronda"))["ronda__min"]
        r1 = Partido.objects.filter(torneo=torneo, ronda=min_ronda)
        # Solo se juegan los 2 cruces de la 1ra ronda; los 6 byes están en ronda 2.
        self.assertEqual(r1.count(), 2)
        cruces_r1 = set()
        for p in r1:
            cruces_r1.add(frozenset([p.placeholder_e1, p.placeholder_e2]))
        self.assertEqual(cruces_r1, {frozenset(["1A", "2B"]), frozenset(["2D", "2E"])})
        # Todos los 10 clasificados aparecen (4 en ronda 1 + 6 byes en ronda 2).
        todos = set()
        for p in Partido.objects.filter(torneo=torneo):
            for ph in (p.placeholder_e1, p.placeholder_e2):
                if ph:
                    todos.add(ph)
        esperados = {f"{k}{z}" for z in "ABCDE" for k in "12"}
        self.assertEqual(todos, esperados)

    def test_generacion_usa_los_cruces(self):
        from torneos.models import FormatoPersonalizado, Partido
        from django.db.models import Min
        fmt = FormatoPersonalizado.objects.create(
            nombre="Manual8", organizacion=self.org, sizes=[3, 3, 3, 3], clasifican_por_grupo=2,
            cruces_manuales=[["1A", "2B"], ["1C", "2D"], ["1B", "2A"], ["1D", "2C"]])
        torneo = Torneo.objects.create(
            nombre="Con Cruces", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=12, estado=Torneo.Estado.ABIERTO, formato_personalizado=fmt)
        for i in range(12):
            j1 = User.objects.create_user(email=f"cm{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"cm{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=torneo, equipo=eq)
        self.client.force_login(self.org_user)
        url = reverse("torneos:admin_manage", kwargs={"pk": torneo.pk})
        self.client.post(url, {"action": "iniciar_torneo"})
        min_ronda = Partido.objects.filter(torneo=torneo).aggregate(Min("ronda"))["ronda__min"]
        r1 = Partido.objects.filter(torneo=torneo, ronda=min_ronda)
        self.assertEqual(r1.count(), 4)
        cruces = set()
        for p in r1:
            cruces.add(frozenset([p.placeholder_e1, p.placeholder_e2]))
        self.assertIn(frozenset(["1A", "2B"]), cruces)
        self.assertIn(frozenset(["1C", "2D"]), cruces)


@override_settings(STORAGES=TEST_STORAGES)
class DashboardOrganizadorTests(TestCase):
    """Panel de métricas del organizador."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgDash", alias="orgdash")
        self.org_user = User.objects.create_user(
            email="dash@t.com", password="x", nombre="D", apellido="A",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.org_user.organizacion = self.org
        self.org_user.save()
        self.torneo = Torneo.objects.create(
            nombre="T Dash", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.ABIERTO)
        for i in range(4):
            j1 = User.objects.create_user(email=f"d{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"d{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=self.torneo, equipo=eq)

    def test_dashboard_requiere_login_admin(self):
        # Anónimo -> redirige
        resp = self.client.get(reverse("torneos:dashboard"))
        self.assertNotEqual(resp.status_code, 200)

    def test_dashboard_muestra_metricas(self):
        self.client.force_login(self.org_user)
        resp = self.client.get(reverse("torneos:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_torneos"], 1)
        self.assertEqual(resp.context["total_inscripciones"], 4)
        self.assertEqual(resp.context["total_jugadores"], 8)
        self.assertEqual(resp.context["ocupacion_pct"], 50)  # 4 de 8 cupos
        self.assertEqual(len(resp.context["proximos"]), 1)

    def test_dashboard_aisla_por_organizacion(self):
        from accounts.models import Organizacion
        otra = Organizacion.objects.create(nombre="Otra", alias="otra")
        Torneo.objects.create(
            nombre="Ajena", division=self.division, organizacion=otra,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.ABIERTO)
        self.client.force_login(self.org_user)
        resp = self.client.get(reverse("torneos:dashboard"))
        self.assertEqual(resp.context["total_torneos"], 1)  # no cuenta la ajena


@override_settings(STORAGES=TEST_STORAGES)
class AislamientoOrganizacionTests(TestCase):
    """Un ORGANIZER no puede operar sobre objetos de OTRA organizacion (IDOR).

    AdminRequiredMixin deja pasar a los organizadores, asi que sin un filtro por
    organizacion alcanzaba con cambiar el pk de la URL.
    """

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Septima", orden=7)
        self.org_a = Organizacion.objects.create(nombre="Club A", alias="club-a")
        self.org_b = Organizacion.objects.create(nombre="Club B", alias="club-b")

        self.user_a = User.objects.create_user(
            email="a@t.com", password="x", nombre="Ana", apellido="A",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.user_a.organizacion = self.org_a
        self.user_a.save()

        # Torneo del club B, con una zona y un partido de zona.
        self.torneo_b = Torneo.objects.create(
            nombre="Torneo del B", division=self.division, organizacion=self.org_b,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.EN_JUEGO)
        self.grupo_b = Grupo.objects.create(torneo=self.torneo_b, nombre="Zona A")

        equipos = []
        for i in range(2):
            j1 = User.objects.create_user(email=f"b{i}a@t.com", password="x", nombre=f"J{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"b{i}b@t.com", password="x", nombre=f"K{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=self.torneo_b, equipo=eq)
            EquipoGrupo.objects.create(grupo=self.grupo_b, equipo=eq)
            equipos.append(eq)
        self.pg_b = PartidoGrupo.objects.create(
            grupo=self.grupo_b, equipo1=equipos[0], equipo2=equipos[1])
        self.partido_b = Partido.objects.create(torneo=self.torneo_b, ronda=1, orden_partido=1)

    def _assert_no_accede(self, url):
        """La vista no debe servir el objeto ajeno (404/403/redirect, nunca 200)."""
        resp = self.client.get(url)
        self.assertNotEqual(
            resp.status_code, 200,
            f"{url} devolvio 200: un organizador de otro club pudo abrir el objeto")

    def test_replace_partido_teams_ajeno(self):
        self.client.force_login(self.user_a)
        self._assert_no_accede(
            reverse("torneos:replace_partido_teams", kwargs={"pk": self.partido_b.pk}))

    def test_replace_partido_grupo_teams_ajeno(self):
        self.client.force_login(self.user_a)
        self._assert_no_accede(
            reverse("torneos:replace_partido_grupo_teams", kwargs={"pk": self.pg_b.pk}))

    def test_swap_group_teams_ajeno(self):
        self.client.force_login(self.user_a)
        self._assert_no_accede(
            reverse("torneos:swap_group_teams", kwargs={"pk": self.grupo_b.pk}))

    def test_el_dueno_si_accede(self):
        """Control: el organizador del club B si puede entrar (no rompimos lo legitimo)."""
        user_b = User.objects.create_user(
            email="bb@t.com", password="x", nombre="Beto", apellido="B",
            genero="OTRO", tipo_usuario="ORGANIZER")
        user_b.organizacion = self.org_b
        user_b.save()
        self.client.force_login(user_b)
        resp = self.client.get(
            reverse("torneos:replace_partido_teams", kwargs={"pk": self.partido_b.pk}))
        self.assertEqual(resp.status_code, 200)

    def test_admin_accede_a_todo(self):
        """Control: un ADMIN no queda filtrado por organizacion."""
        admin = User.objects.create_user(
            email="adm@t.com", password="x", nombre="Adm", apellido="In",
            genero="OTRO", tipo_usuario="ADMIN")
        self.client.force_login(admin)
        resp = self.client.get(
            reverse("torneos:replace_partido_teams", kwargs={"pk": self.partido_b.pk}))
        self.assertEqual(resp.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class RendimientoTablaPosicionesTests(TestCase):
    """El signal que recalcula la tabla de zona corre en CADA resultado cargado.

    Antes lanzaba 2 queries por equipo del grupo; ahora es un numero fijo.
    Este test lo fija para que no vuelva a degradarse.
    """

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Octava", orden=8)
        self.org = Organizacion.objects.create(nombre="OrgPerf", alias="orgperf")
        self.torneo = Torneo.objects.create(
            nombre="Perf", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.EN_JUEGO)
        self.grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        self.equipos = []
        for i in range(4):
            j1 = User.objects.create_user(email=f"p{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"p{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            Inscripcion.objects.create(torneo=self.torneo, equipo=eq)
            EquipoGrupo.objects.create(grupo=self.grupo, equipo=eq)
            self.equipos.append(eq)

    def test_la_tabla_se_calcula_bien(self):
        """Correccion antes que velocidad: los numeros tienen que dar."""
        p = PartidoGrupo.objects.create(
            grupo=self.grupo, equipo1=self.equipos[0], equipo2=self.equipos[1])
        p.e1_sets_ganados = 2
        p.e2_sets_ganados = 0
        p.e1_games_ganados = 12
        p.e2_games_ganados = 6
        p.ganador = self.equipos[0]
        p.save()

        ganador = EquipoGrupo.objects.get(grupo=self.grupo, equipo=self.equipos[0])
        perdedor = EquipoGrupo.objects.get(grupo=self.grupo, equipo=self.equipos[1])
        sin_jugar = EquipoGrupo.objects.get(grupo=self.grupo, equipo=self.equipos[2])

        self.assertEqual(ganador.partidos_jugados, 1)
        self.assertEqual(ganador.partidos_ganados, 1)
        self.assertEqual(ganador.partidos_perdidos, 0)
        self.assertEqual(ganador.sets_a_favor, 2)
        self.assertEqual(ganador.sets_en_contra, 0)
        self.assertEqual(ganador.diferencia_sets, 2)
        self.assertEqual(ganador.diferencia_games, 6)

        self.assertEqual(perdedor.partidos_ganados, 0)
        self.assertEqual(perdedor.partidos_perdidos, 1)
        self.assertEqual(perdedor.diferencia_sets, -2)
        self.assertEqual(perdedor.diferencia_games, -6)

        # El que no jugo queda en cero, no con basura.
        self.assertEqual(sin_jugar.partidos_jugados, 0)
        self.assertEqual(sin_jugar.diferencia_sets, 0)

    def _queries_del_recalculo(self, grupo, partido):
        """Cuenta las queries del recalculo de la tabla de `grupo`."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from torneos.signals import actualizar_tabla_de_posiciones

        with CaptureQueriesContext(connection) as ctx:
            actualizar_tabla_de_posiciones(PartidoGrupo, partido)
        return len(ctx.captured_queries)

    def test_el_recalculo_son_3_queries(self):
        """Filas de la tabla + partidos jugados + bulk_update. Nada por equipo."""
        p = PartidoGrupo.objects.create(
            grupo=self.grupo, equipo1=self.equipos[0], equipo2=self.equipos[1])
        # Sin ganador no se dispara la invalidacion de cache, asi que medimos
        # unicamente el recalculo.
        self.assertEqual(self._queries_del_recalculo(self.grupo, p), 3)

    def test_no_crece_con_la_cantidad_de_equipos(self):
        """Una zona de 8 tiene que costar lo mismo que una de 4."""
        p4 = PartidoGrupo.objects.create(
            grupo=self.grupo, equipo1=self.equipos[0], equipo2=self.equipos[1])
        queries_zona_de_4 = self._queries_del_recalculo(self.grupo, p4)

        grupo8 = Grupo.objects.create(torneo=self.torneo, nombre="Zona B")
        equipos8 = []
        for i in range(8):
            j1 = User.objects.create_user(email=f"q{i}a@t.com", password="x", nombre=f"C{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"q{i}b@t.com", password="x", nombre=f"D{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            EquipoGrupo.objects.create(grupo=grupo8, equipo=eq)
            equipos8.append(eq)
        p8 = PartidoGrupo.objects.create(
            grupo=grupo8, equipo1=equipos8[0], equipo2=equipos8[1])
        queries_zona_de_8 = self._queries_del_recalculo(grupo8, p8)

        self.assertEqual(
            queries_zona_de_4, queries_zona_de_8,
            "El recalculo escala con la cantidad de equipos: volvio el N+1")


@override_settings(STORAGES=TEST_STORAGES)
class CuposYExportTests(TestCase):
    """Cupos con tope real y export de inscriptos."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Primera", orden=1)
        self.org = Organizacion.objects.create(nombre="OrgCupos", alias="orgcupos")
        self.org_user = User.objects.create_user(
            email="oc@t.com", password="x", nombre="O", apellido="C",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.org_user.organizacion = self.org
        self.org_user.save()
        self.torneo = Torneo.objects.create(
            nombre="Torneo Chico", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=5),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=2, estado=Torneo.Estado.ABIERTO)

    def _pareja(self, i):
        j1 = User.objects.create_user(email=f"c{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division, genero="MASCULINO")
        j2 = User.objects.create_user(email=f"c{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division, genero="MASCULINO")
        j1.numero_telefono = f"+54911{i:07d}"
        j1.save()
        return j1, Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)

    def test_no_se_puede_pasar_del_cupo(self):
        """Un POST directo no debe entrar cuando el torneo esta lleno."""
        for i in range(2):
            _, eq = self._pareja(i)
            Inscripcion.objects.create(torneo=self.torneo, equipo=eq)
        self.assertEqual(self.torneo.cupos_disponibles, 0)

        jugador, _ = self._pareja(9)
        self.client.force_login(jugador)
        url = reverse("torneos:inscribirse", kwargs={"torneo_pk": self.torneo.pk})
        self.client.post(url, {})
        self.assertEqual(
            Inscripcion.objects.filter(torneo=self.torneo).count(), 2,
            "Entro una inscripcion por encima del cupo")

    def test_export_csv_del_dueno(self):
        _, eq = self._pareja(0)
        Inscripcion.objects.create(torneo=self.torneo, equipo=eq)
        self.client.force_login(self.org_user)
        resp = self.client.get(
            reverse("torneos:exportar_inscriptos", kwargs={"pk": self.torneo.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("attachment", resp["Content-Disposition"])
        cuerpo = resp.content.decode("utf-8-sig")
        self.assertIn("Pareja", cuerpo)
        self.assertIn(eq.nombre, cuerpo)

    def test_export_csv_aislado_por_organizacion(self):
        """Un organizador de otro club no puede bajarse los inscriptos."""
        from accounts.models import Organizacion
        otra = Organizacion.objects.create(nombre="Otra", alias="otra-exp")
        ajeno = User.objects.create_user(
            email="aj@t.com", password="x", nombre="Aj", apellido="Eno",
            genero="OTRO", tipo_usuario="ORGANIZER")
        ajeno.organizacion = otra
        ajeno.save()
        self.client.force_login(ajeno)
        resp = self.client.get(
            reverse("torneos:exportar_inscriptos", kwargs={"pk": self.torneo.pk}))
        self.assertNotEqual(resp.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class CircuitoAdminTests(TestCase):
    """CRUD de circuitos: el motor ya existia, faltaba la pantalla."""

    def setUp(self):
        from accounts.models import Organizacion
        from torneos.models import Circuito
        self.division = Division.objects.create(nombre="Segunda", orden=2)
        self.org = Organizacion.objects.create(nombre="OrgCirc", alias="orgcirc")
        self.otra = Organizacion.objects.create(nombre="OtraCirc", alias="otracirc")
        self.org_user = User.objects.create_user(
            email="ci@t.com", password="x", nombre="C", apellido="I",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.org_user.organizacion = self.org
        self.org_user.save()
        self.circuito_ajeno = Circuito.objects.create(
            nombre="Circuito Ajeno", organizacion=self.otra)

    def test_crear_circuito(self):
        from torneos.models import Circuito
        self.client.force_login(self.org_user)
        resp = self.client.post(reverse("torneos:circuito_crear"), {
            "nombre": "Circuito Verano",
            "descripcion": "Liga de verano",
            "activo": "on",
            "cupos_ascenso": 2,
            "cupos_descenso": 2,
        })
        self.assertIn(resp.status_code, (301, 302))
        creado = Circuito.objects.get(nombre="Circuito Verano")
        self.assertEqual(creado.organizacion, self.org, "No quedo atado a su organizacion")

    def test_lista_solo_muestra_los_propios(self):
        from torneos.models import Circuito
        Circuito.objects.create(nombre="Mio", organizacion=self.org)
        self.client.force_login(self.org_user)
        resp = self.client.get(reverse("torneos:circuito_admin_list"))
        self.assertEqual(resp.status_code, 200)
        nombres = [c.nombre for c in resp.context["circuitos"]]
        self.assertIn("Mio", nombres)
        self.assertNotIn("Circuito Ajeno", nombres)

    def test_no_puede_editar_circuito_ajeno(self):
        self.client.force_login(self.org_user)
        resp = self.client.get(
            reverse("torneos:circuito_editar", kwargs={"pk": self.circuito_ajeno.pk}))
        self.assertNotEqual(resp.status_code, 200)

    def test_solo_ofrece_sus_torneos(self):
        """El selector de torneos no debe listar los de otro club."""
        mio = Torneo.objects.create(
            nombre="Mi torneo", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8)
        ajeno = Torneo.objects.create(
            nombre="Torneo ajeno", division=self.division, organizacion=self.otra,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8)
        from torneos.forms import CircuitoForm
        form = CircuitoForm(actor=self.org_user)
        qs = form.fields["torneos"].queryset
        self.assertIn(mio, qs)
        self.assertNotIn(ajeno, qs)


@override_settings(STORAGES=TEST_STORAGES)
class FiltrosTorneosTests(TestCase):
    """Filtros por ciudad, division y categoria en los listados publicos."""

    def setUp(self):
        from accounts.models import Organizacion
        self.d5 = Division.objects.create(nombre="Quinta", orden=5)
        self.d6 = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgF", alias="orgf")

        def crear(nombre, division, ciudad, categoria):
            return Torneo.objects.create(
                nombre=nombre, division=division, organizacion=self.org,
                ciudad=ciudad, categoria=categoria,
                fecha_inicio=timezone.now().date() + timedelta(days=3),
                fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
                cupos_totales=16, estado=Torneo.Estado.ABIERTO)

        self.rosario = crear("Abierto Rosario", self.d5, "Rosario", "M")
        self.mardel = crear("Abierto Mar del Plata", self.d6, "Mar del Plata", "F")

    def _nombres(self, resp):
        return [t.nombre for t in resp.context["torneos_abiertos"]]

    def test_sin_filtros_trae_todo(self):
        resp = self.client.get(reverse("torneos:abierto_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertCountEqual(
            self._nombres(resp), ["Abierto Rosario", "Abierto Mar del Plata"])

    def test_filtro_por_ciudad(self):
        resp = self.client.get(reverse("torneos:abierto_list"), {"ciudad": "Rosario"})
        self.assertEqual(self._nombres(resp), ["Abierto Rosario"])

    def test_filtro_por_division(self):
        resp = self.client.get(
            reverse("torneos:abierto_list"), {"division": self.d6.pk})
        self.assertEqual(self._nombres(resp), ["Abierto Mar del Plata"])

    def test_filtro_por_categoria(self):
        resp = self.client.get(reverse("torneos:abierto_list"), {"categoria": "F"})
        self.assertEqual(self._nombres(resp), ["Abierto Mar del Plata"])

    def test_filtros_combinados_sin_resultados(self):
        resp = self.client.get(reverse("torneos:abierto_list"),
                               {"ciudad": "Rosario", "categoria": "F"})
        self.assertEqual(self._nombres(resp), [])
        self.assertTrue(resp.context["hay_filtros"])

    def test_valores_basura_no_rompen(self):
        """Un parametro invalido no debe reventar la pagina."""
        for params in ({"division": "abc"}, {"categoria": "ZZZ"}, {"ciudad": "'; DROP TABLE"}):
            resp = self.client.get(reverse("torneos:abierto_list"), params)
            self.assertEqual(resp.status_code, 200, f"rompio con {params}")

    def test_las_opciones_de_ciudad_salen_de_los_torneos(self):
        resp = self.client.get(reverse("torneos:abierto_list"))
        self.assertCountEqual(resp.context["ciudades"], ["Rosario", "Mar del Plata"])

    def test_la_paginacion_conserva_los_filtros(self):
        from django.template import Context, Template
        from django.test import RequestFactory
        req = RequestFactory().get("/torneos/abiertos/", {"ciudad": "Rosario", "page": "1"})
        t = Template("{% load torneo_extras %}{% query_con page=2 %}")
        salida = t.render(Context({"request": req}))
        self.assertIn("ciudad=Rosario", salida)
        self.assertIn("page=2", salida)

    def test_en_juego_tambien_filtra(self):
        self.rosario.estado = Torneo.Estado.EN_JUEGO
        self.rosario.save()
        resp = self.client.get(reverse("torneos:en_juego_list"), {"ciudad": "Rosario"})
        self.assertEqual(
            [t.nombre for t in resp.context["torneos_en_juego"]], ["Abierto Rosario"])


@override_settings(STORAGES=TEST_STORAGES)
class DatosDePagoTests(TestCase):
    """Datos para pagar la inscripcion (pedido de un organizador real)."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Tercera", orden=3)
        self.org = Organizacion.objects.create(
            nombre="Club Pago", alias="club-pago",
            alias_cobro="Buccellalean05",
            titular_cobro="Leandro Buccella",
            whatsapps_comprobante="+54 9 223 593-7115, +54 9 223 633-7881")
        self.torneo = Torneo.objects.create(
            nombre="Torneo Pago", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=5),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO,
            precio_inscripcion=80000, senia=40000)

    def test_la_ficha_muestra_los_datos_de_pago(self):
        resp = self.client.get(reverse("torneos:detail", kwargs={"pk": self.torneo.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Buccellalean05", html)
        self.assertIn("Leandro Buccella", html)
        self.assertIn("80000", html.replace(".", "").replace(",", ""))
        self.assertIn("40000", html.replace(".", "").replace(",", ""))

    def test_los_whatsapp_quedan_como_link_wa_me(self):
        resp = self.client.get(reverse("torneos:detail", kwargs={"pk": self.torneo.pk}))
        html = resp.content.decode()
        # Solo digitos, sin espacios ni guiones
        self.assertIn("wa.me/5492235937115", html)
        self.assertIn("wa.me/5492236337881", html)

    def test_parseo_de_varios_whatsapp(self):
        lista = self.org.whatsapps_comprobante_lista
        self.assertEqual(len(lista), 2)
        self.assertEqual(lista[0][1], "5492235937115")
        self.assertEqual(lista[1][1], "5492236337881")

    def test_sin_precio_no_se_muestra_el_bloque(self):
        """Un torneo gratis no debe mostrar un panel de pago vacio."""
        self.torneo.precio_inscripcion = None
        self.torneo.save()
        resp = self.client.get(reverse("torneos:detail", kwargs={"pk": self.torneo.pk}))
        self.assertNotIn("Cómo pagar la inscripción", resp.content.decode())

    def test_sin_alias_no_se_muestra_el_bloque(self):
        """Si el organizador no cargo el alias, el panel no sirve de nada."""
        self.org.alias_cobro = ""
        self.org.save()
        resp = self.client.get(reverse("torneos:detail", kwargs={"pk": self.torneo.pk}))
        self.assertNotIn("Cómo pagar la inscripción", resp.content.decode())

    def test_la_senia_es_opcional(self):
        self.torneo.senia = None
        self.torneo.save()
        resp = self.client.get(reverse("torneos:detail", kwargs={"pk": self.torneo.pk}))
        html = resp.content.decode()
        self.assertIn("Cómo pagar la inscripción", html)
        self.assertNotIn("para reservar el lugar", html)


@override_settings(STORAGES=TEST_STORAGES)
class OrganizadorEditaDatosDePagoTests(TestCase):
    """El organizador tiene que poder cambiar precios y datos de cobro SOLO,
    sin depender de nadie. Los templates renderizan campo por campo, asi que un
    campo nuevo en el form no aparece si no se agrega al HTML: esto lo verifica.
    """

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Cuarta", orden=4)
        self.org = Organizacion.objects.create(nombre="Club Edita", alias="club-edita")
        self.organizador = User.objects.create_user(
            email="oe@t.com", password="x", nombre="Or", apellido="Ed",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.organizador.organizacion = self.org
        self.organizador.save()
        self.torneo = Torneo.objects.create(
            nombre="Editable", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=5),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO)

    def test_los_datos_de_cobro_aparecen_en_ajustes(self):
        self.client.force_login(self.organizador)
        resp = self.client.get(reverse("accounts:organizacion_settings"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for campo in ("alias_cobro", "titular_cobro", "whatsapps_comprobante"):
            self.assertIn(
                f'name="{campo}"', html,
                f"El campo {campo} no se puede editar desde la web")

    def test_el_organizador_guarda_sus_datos_de_cobro(self):
        self.client.force_login(self.organizador)
        resp = self.client.post(reverse("accounts:organizacion_settings"), {
            "nombre": self.org.nombre,
            "alias": self.org.alias,
            "descripcion": "",
            "whatsapp": "",
            "direccion": "",
            "alias_cobro": "miclub.padel",
            "titular_cobro": "Juan Perez",
            "whatsapps_comprobante": "+54 9 223 111-2222",
        })
        self.assertIn(resp.status_code, (200, 301, 302))
        self.org.refresh_from_db()
        self.assertEqual(self.org.alias_cobro, "miclub.padel")
        self.assertEqual(self.org.titular_cobro, "Juan Perez")

    def test_los_precios_aparecen_en_el_form_del_torneo(self):
        self.client.force_login(self.organizador)
        resp = self.client.get(
            reverse("torneos:admin_editar", kwargs={"pk": self.torneo.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        for campo in ("precio_inscripcion", "senia", "instrucciones_pago"):
            self.assertIn(
                f'name="{campo}"', html,
                f"El campo {campo} no se puede editar desde la web")


@override_settings(STORAGES=TEST_STORAGES)
class CobrosTests(TestCase):
    """Panel de cobros y carga de comprobante."""

    def setUp(self):
        from accounts.models import Organizacion
        from torneos.models import EstadoPago
        self.EstadoPago = EstadoPago
        self.division = Division.objects.create(nombre="Quinta", orden=5)
        self.org = Organizacion.objects.create(
            nombre="Club Cobro", alias="club-cobro", alias_cobro="mi.alias")
        self.organizador = User.objects.create_user(
            email="oc2@t.com", password="x", nombre="Or", apellido="Co",
            genero="OTRO", tipo_usuario="ORGANIZER")
        self.organizador.organizacion = self.org
        self.organizador.save()
        self.torneo = Torneo.objects.create(
            nombre="Con Precio", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=5),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO,
            precio_inscripcion=80000, senia=40000)

        self.inscripciones = []
        for i in range(3):
            j1 = User.objects.create_user(email=f"co{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"co{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division)
            eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
            self.inscripciones.append(
                Inscripcion.objects.create(torneo=self.torneo, equipo=eq))
        self.jugador = self.inscripciones[0].equipo.jugador1

    def test_por_defecto_todo_pendiente(self):
        for i in self.inscripciones:
            self.assertEqual(i.estado_pago, self.EstadoPago.PENDIENTE)
            self.assertFalse(i.pago_al_dia)

    def test_el_organizador_marca_un_pago(self):
        self.client.force_login(self.organizador)
        resp = self.client.post(
            reverse("torneos:cobros", kwargs={"pk": self.torneo.pk}), {
                "inscripcion_id": self.inscripciones[0].pk,
                "estado_pago": self.EstadoPago.PAGADO,
                "monto": "80000",
                "nota_pago": "transferencia ok",
            })
        self.assertIn(resp.status_code, (301, 302))
        i = self.inscripciones[0]
        i.refresh_from_db()
        self.assertEqual(i.estado_pago, self.EstadoPago.PAGADO)
        self.assertEqual(i.monto_pagado, 80000)
        self.assertIsNotNone(i.fecha_pago, "No se sello la fecha de pago")
        self.assertTrue(i.pago_al_dia)

    def test_volver_a_pendiente_limpia_la_fecha(self):
        from torneos.services.pagos import marcar_pago
        i = self.inscripciones[0]
        marcar_pago(i, self.EstadoPago.PAGADO, monto=80000)
        self.assertIsNotNone(i.fecha_pago)
        marcar_pago(i, self.EstadoPago.PENDIENTE)
        self.assertIsNone(i.fecha_pago)

    def test_el_resumen_suma_bien(self):
        from torneos.services.pagos import marcar_pago, resumen_de_cobros
        marcar_pago(self.inscripciones[0], self.EstadoPago.PAGADO, monto=80000)
        marcar_pago(self.inscripciones[1], self.EstadoPago.SENADO, monto=40000)
        r = resumen_de_cobros(self.torneo)
        self.assertEqual(r["total"], 3)
        self.assertEqual(r["pagados"], 1)
        self.assertEqual(r["senados"], 1)
        self.assertEqual(r["pendientes"], 1)
        self.assertEqual(r["recaudado"], 120000)
        self.assertEqual(r["esperado"], 240000)   # 3 x 80.000
        self.assertEqual(r["falta"], 120000)

    def test_los_exentos_no_se_esperan_cobrar(self):
        from torneos.services.pagos import marcar_pago, resumen_de_cobros
        marcar_pago(self.inscripciones[0], self.EstadoPago.EXENTO)
        r = resumen_de_cobros(self.torneo)
        self.assertEqual(r["esperado"], 160000, "El exento no deberia sumar al esperado")

    def test_estado_invalido_no_rompe(self):
        self.client.force_login(self.organizador)
        resp = self.client.post(
            reverse("torneos:cobros", kwargs={"pk": self.torneo.pk}), {
                "inscripcion_id": self.inscripciones[0].pk,
                "estado_pago": "ZZ",
            })
        self.assertIn(resp.status_code, (301, 302))
        self.inscripciones[0].refresh_from_db()
        self.assertEqual(self.inscripciones[0].estado_pago, self.EstadoPago.PENDIENTE)

    def test_cobros_aislado_por_organizacion(self):
        from accounts.models import Organizacion
        otra = Organizacion.objects.create(nombre="Otro Club", alias="otro-club")
        ajeno = User.objects.create_user(
            email="aje@t.com", password="x", nombre="Aj", apellido="En",
            genero="OTRO", tipo_usuario="ORGANIZER")
        ajeno.organizacion = otra
        ajeno.save()
        self.client.force_login(ajeno)
        resp = self.client.get(reverse("torneos:cobros", kwargs={"pk": self.torneo.pk}))
        self.assertNotEqual(resp.status_code, 200)

    def test_no_se_puede_subir_comprobante_ajeno(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        otro_jugador = self.inscripciones[1].equipo.jugador1
        self.client.force_login(otro_jugador)
        archivo = SimpleUploadedFile("c.jpg", b"falso", content_type="image/jpeg")
        resp = self.client.post(
            reverse("torneos:subir_comprobante", kwargs={"pk": self.inscripciones[0].pk}),
            {"comprobante": archivo})
        self.assertIn(resp.status_code, (403, 404))
        self.inscripciones[0].refresh_from_db()
        self.assertFalse(bool(self.inscripciones[0].comprobante))


@override_settings(STORAGES=TEST_STORAGES)
class RecordatoriosTests(TestCase):
    """Recordatorios de partido: primera notificacion disparada por tiempo."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgRec", alias="orgrec")
        self.torneo = Torneo.objects.create(
            nombre="Con Horarios", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.EN_JUEGO)
        self.equipos = []
        for i in range(2):
            j1 = User.objects.create_user(email=f"re{i}a@t.com", password="x", nombre=f"A{i}", apellido="X", division=self.division)
            j2 = User.objects.create_user(email=f"re{i}b@t.com", password="x", nombre=f"B{i}", apellido="Y", division=self.division)
            self.equipos.append(Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division))

    def _partido(self, horas_desde_ahora):
        return Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.equipos[0], equipo2=self.equipos[1],
            fecha_hora=timezone.now() + timedelta(hours=horas_desde_ahora))

    def test_detecta_la_ventana_de_24h(self):
        from torneos.services.recordatorios import partidos_a_recordar
        self._partido(24)
        pendientes = partidos_a_recordar()
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0][1], "24h")

    def test_detecta_la_ventana_de_2h(self):
        from torneos.services.recordatorios import partidos_a_recordar
        self._partido(2)
        pendientes = partidos_a_recordar()
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0][1], "2h")

    def test_un_partido_lejano_no_dispara_nada(self):
        from torneos.services.recordatorios import partidos_a_recordar
        self._partido(72)
        self.assertEqual(partidos_a_recordar(), [])

    def test_no_recuerda_partidos_ya_jugados(self):
        from torneos.services.recordatorios import partidos_a_recordar
        p = self._partido(2)
        p.ganador = self.equipos[0]
        p.save()
        self.assertEqual(partidos_a_recordar(), [])

    def test_no_recuerda_partidos_sin_horario(self):
        from torneos.services.recordatorios import partidos_a_recordar
        Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=2,
            equipo1=self.equipos[0], equipo2=self.equipos[1])
        self.assertEqual(partidos_a_recordar(), [])

    def test_es_idempotente(self):
        """Correr el cron dos veces no debe notificar dos veces: es LO importante."""
        from torneos.services.recordatorios import enviar_recordatorios
        p = self._partido(2)

        partidos, jugadores = enviar_recordatorios()
        self.assertEqual(partidos, 1)
        self.assertEqual(jugadores, 4)

        p.refresh_from_db()
        self.assertIn("2h", p.recordatorios_enviados)

        # Segunda corrida: nada
        partidos2, jugadores2 = enviar_recordatorios()
        self.assertEqual(partidos2, 0, "Se volvio a notificar el mismo partido")

    def test_las_dos_ventanas_se_mandan_por_separado(self):
        """Recordado a 24h, tiene que volver a recordarse a 2h."""
        from torneos.services.recordatorios import enviar_recordatorios, partidos_a_recordar
        p = self._partido(24)
        enviar_recordatorios()
        p.refresh_from_db()
        self.assertEqual(p.recordatorios_enviados, ["24h"])

        # Ahora simulamos que falta poco: movemos el partido, no el reloj
        p.fecha_hora = timezone.now() + timedelta(hours=2)
        p.save()
        pendientes = partidos_a_recordar()
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0][1], "2h")

    def test_dry_run_no_marca_nada(self):
        from torneos.services.recordatorios import enviar_recordatorios
        p = self._partido(2)
        enviar_recordatorios(dry_run=True)
        p.refresh_from_db()
        self.assertEqual(p.recordatorios_enviados, [])

    def test_tambien_recuerda_partidos_de_zona(self):
        from torneos.services.recordatorios import partidos_a_recordar
        grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        PartidoGrupo.objects.create(
            grupo=grupo, equipo1=self.equipos[0], equipo2=self.equipos[1],
            fecha_hora=timezone.now() + timedelta(hours=2))
        pendientes = partidos_a_recordar()
        self.assertEqual(len(pendientes), 1)


@override_settings(STORAGES=TEST_STORAGES)
class PlacasNuevasTests(TestCase):
    """Placas de jugador y de resultado, sobre el pipeline 9:16 ya existente."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Cuarta", orden=4)
        self.org = Organizacion.objects.create(nombre="Club Placa", alias="club-placa")
        self.j1 = User.objects.create_user(
            email="pl1@t.com", password="x", nombre="Lionel", apellido="Perez",
            division=self.division, genero="MASCULINO")
        self.j2 = User.objects.create_user(
            email="pl2@t.com", password="x", nombre="Diego", apellido="Gomez",
            division=self.division, genero="MASCULINO")
        self.j3 = User.objects.create_user(
            email="pl3@t.com", password="x", nombre="Juan", apellido="Lopez",
            division=self.division, genero="MASCULINO")
        self.j4 = User.objects.create_user(
            email="pl4@t.com", password="x", nombre="Pedro", apellido="Diaz",
            division=self.division, genero="MASCULINO")
        self.eq1 = Equipo.objects.create(jugador1=self.j1, jugador2=self.j2, division=self.division)
        self.eq2 = Equipo.objects.create(jugador1=self.j3, jugador2=self.j4, division=self.division)
        self.torneo = Torneo.objects.create(
            nombre="Torneo Placa", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
            cupos_totales=8, estado=Torneo.Estado.EN_JUEGO)
        self.partido = Partido.objects.create(
            torneo=self.torneo, ronda=1, orden_partido=1,
            equipo1=self.eq1, equipo2=self.eq2)

    def test_placa_de_jugador_renderiza(self):
        resp = self.client.get(
            reverse("torneos:placa_jugador", kwargs={"pk": self.j1.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Lionel Perez", html)
        self.assertIn("Cuarta", html)

    def test_la_placa_de_jugador_es_publica(self):
        """Se comparte, asi que no puede pedir login."""
        resp = self.client.get(
            reverse("torneos:placa_jugador", kwargs={"pk": self.j1.pk}))
        self.assertEqual(resp.status_code, 200)

    def test_no_hay_placa_de_un_dummy(self):
        dummy = User.objects.create_user(
            email="dummy@x.local", password="x", nombre="Dum", apellido="My",
            division=self.division)
        dummy.is_dummy = True
        dummy.save()
        resp = self.client.get(
            reverse("torneos:placa_jugador", kwargs={"pk": dummy.pk}))
        self.assertEqual(resp.status_code, 404)

    def test_placa_de_resultado_muestra_el_ganador(self):
        self.partido.ganador = self.eq1
        self.partido.e1_sets_ganados = 2
        self.partido.resultado = "6-4 6-3"   # en Partido es un campo, no property
        self.partido.save()

        resp = self.client.get(reverse(
            "torneos:placa_resultado", kwargs={"tipo": "llave", "pk": self.partido.pk}))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("6-4 6-3", html)
        self.assertIn(self.eq1.nombre, html)
        self.assertIn(self.eq2.nombre, html)

    def test_placa_de_resultado_de_zona(self):
        grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        pg = PartidoGrupo.objects.create(
            grupo=grupo, equipo1=self.eq1, equipo2=self.eq2,
            ganador=self.eq1, e1_set1=6, e2_set1=2, e1_set2=6, e2_set2=2)
        resp = self.client.get(reverse(
            "torneos:placa_resultado", kwargs={"tipo": "zona", "pk": pg.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Zona A", resp.content.decode())

    def test_los_datos_del_jugador_salen_de_las_stats_reales(self):
        from torneos.services.placas import datos_placa_jugador
        datos = datos_placa_jugador(self.j1)
        for clave in ("nombre", "division", "win_rate", "victorias", "partidos_jugados"):
            self.assertIn(clave, datos)
        self.assertEqual(datos["nombre"], "Lionel Perez")
        self.assertEqual(datos["iniciales"], "LP")

    def test_solo_muestra_logros_conseguidos(self):
        """Una placa con casilleros vacios no se comparte."""
        from torneos.services.placas import datos_placa_jugador
        datos = datos_placa_jugador(self.j1)
        for logro in datos["logros"]:
            self.assertTrue(logro["unlocked"], f"Logro bloqueado en la placa: {logro}")


@override_settings(STORAGES=TEST_STORAGES)
class EmbudoInscripcionTests(TestCase):
    """El comando que mide donde se cae la gente antes de inscribirse."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgEmb", alias="orgemb")
        self.torneo = Torneo.objects.create(
            nombre="Embudo", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=5),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=2),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO)

    def _jugador(self, i, telefono=""):
        u = User.objects.create_user(
            email=f"emb{i}@t.com", password="x", nombre=f"J{i}", apellido="X",
            division=self.division)
        if telefono:
            u.numero_telefono = telefono
            u.save()
        return u

    def _salida(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("embudo_inscripcion", stdout=out)
        return out.getvalue()

    def test_cuenta_los_tres_escalones(self):
        # 6 jugadores: 4 arman pareja, y solo 2 de esos se inscriben
        js = [self._jugador(i) for i in range(6)]
        eq1 = Equipo.objects.create(jugador1=js[0], jugador2=js[1], division=self.division)
        Equipo.objects.create(jugador1=js[2], jugador2=js[3], division=self.division)
        Inscripcion.objects.create(torneo=self.torneo, equipo=eq1)

        salida = self._salida()
        self.assertIn("Crearon cuenta", salida)
        # 6 con cuenta, 4 con pareja, 2 inscriptos
        self.assertRegex(salida, r"Crearon cuenta\s+6")
        self.assertRegex(salida, r"Formaron pareja\s+4")
        self.assertRegex(salida, r"Se inscribieron a un torneo\s+2")

    def test_no_cuenta_a_los_dummy(self):
        real = self._jugador(0)
        dummy = User.objects.create_user(
            email="dum@x.local", password="x", nombre="D", apellido="X",
            division=self.division)
        dummy.is_dummy = True
        dummy.save()
        salida = self._salida()
        self.assertRegex(salida, r"Crearon cuenta\s+1")

    def test_reporta_cuantos_tienen_telefono(self):
        """Si el % es alto, el flujo de invitar por WhatsApp es viable."""
        self._jugador(0, telefono="+5492235551111")
        self._jugador(1)
        salida = self._salida()
        self.assertIn("jugadores con teléfono: 1 de 2", salida)

    def test_sin_jugadores_no_rompe(self):
        salida = self._salida()
        self.assertIn("No hay jugadores para medir", salida)


@override_settings(STORAGES=TEST_STORAGES)
class EmbudoWebTests(TestCase):
    """El embudo tiene que verse desde la web: no hay shell en Render."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Primera", orden=1)
        self.admin = User.objects.create_user(
            email="adm@emb.com", password="x", nombre="Ad", apellido="Min",
            genero="OTRO", tipo_usuario="ADMIN")
        self.jugador = User.objects.create_user(
            email="jug@emb.com", password="x", nombre="Ju", apellido="Ga",
            division=self.division)

    def test_la_pagina_carga_para_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("torneos:embudo"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Crearon cuenta", resp.content.decode())

    def test_un_jugador_no_entra(self):
        self.client.force_login(self.jugador)
        resp = self.client.get(reverse("torneos:embudo"))
        self.assertNotEqual(resp.status_code, 200)

    def test_anonimo_no_entra(self):
        resp = self.client.get(reverse("torneos:embudo"))
        self.assertNotEqual(resp.status_code, 200)

    def test_el_filtro_de_dias_no_rompe_con_basura(self):
        self.client.force_login(self.admin)
        for valor in ("abc", "-5", "999999"):
            resp = self.client.get(reverse("torneos:embudo"), {"dias": valor})
            self.assertEqual(resp.status_code, 200, f"rompio con dias={valor}")

    def test_los_numeros_coinciden_con_el_comando(self):
        """La web y el comando tienen que dar lo mismo: comparten el service."""
        from io import StringIO
        from django.core.management import call_command
        from torneos.services.embudo import calcular_embudo

        eq = Equipo.objects.create(
            jugador1=self.jugador,
            jugador2=User.objects.create_user(
                email="j2@emb.com", password="x", nombre="Se", apellido="Gu",
                division=self.division),
            division=self.division)

        datos = calcular_embudo()
        out = StringIO()
        call_command("embudo_inscripcion", stdout=out)
        salida = out.getvalue()

        self.assertIn(str(datos["total"]), salida)
        self.assertEqual(datos["con_pareja"], 2)


@override_settings(STORAGES=TEST_STORAGES)
class InscripcionDirectaTests(TestCase):
    """Anotarse armando la pareja en el mismo paso, sin esperar que el otro acepte."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgDir", alias="orgdir")
        self.torneo = Torneo.objects.create(
            nombre="Torneo Directo", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=7),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=3),
            cupos_totales=8, estado=Torneo.Estado.ABIERTO)
        self.yo = User.objects.create_user(
            email="yo@dir.com", password="x", nombre="Yo", apellido="Mismo",
            division=self.division, genero="MASCULINO")
        self.otro = User.objects.create_user(
            email="otro@dir.com", password="x", nombre="Otro", apellido="Jugador",
            division=self.division, genero="MASCULINO")

    def _url(self):
        return reverse("torneos:inscribirse_con_companero",
                       kwargs={"torneo_pk": self.torneo.pk})

    def test_se_anota_con_alguien_que_ya_tiene_cuenta(self):
        self.client.force_login(self.yo)
        resp = self.client.post(self._url(), {
            "modo": "existente", "companero": self.otro.pk})
        self.assertIn(resp.status_code, (301, 302))

        self.assertEqual(Inscripcion.objects.filter(torneo=self.torneo).count(), 1,
                         "No quedo inscripta la pareja")
        equipo = Equipo.objects.filter(esta_activo=True).first()
        self.assertIsNotNone(equipo)
        self.assertIn(self.yo.pk, (equipo.jugador1_id, equipo.jugador2_id))
        self.assertIn(self.otro.pk, (equipo.jugador1_id, equipo.jugador2_id))

    def test_no_espera_que_el_otro_acepte(self):
        """El punto de todo el cambio: la inscripcion existe YA."""
        from equipos.models import Invitation
        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": self.otro.pk})

        inv = Invitation.objects.filter(inviter=self.yo, invited=self.otro).first()
        self.assertIsNotNone(inv, "Deberia avisarle al companero")
        self.assertEqual(inv.status, Invitation.Status.PENDING)
        self.assertTrue(Inscripcion.objects.filter(torneo=self.torneo).exists())

    def test_se_anota_con_alguien_sin_cuenta(self):
        self.client.force_login(self.yo)
        resp = self.client.post(self._url(), {
            "modo": "nuevo", "nombre": "Carlos", "apellido": "Nuevo",
            "telefono": "+54 9 223 555-7788"})
        self.assertIn(resp.status_code, (301, 302))

        creado = User.objects.filter(nombre="Carlos", apellido="Nuevo").first()
        self.assertIsNotNone(creado, "No se creo el companero")
        self.assertTrue(creado.is_dummy)
        self.assertFalse(creado.is_active, "No deberia poder loguear todavia")
        self.assertTrue(Inscripcion.objects.filter(torneo=self.torneo).exists())

    def test_no_duplica_a_alguien_que_ya_esta_por_telefono(self):
        """Si el telefono ya existe, se usa esa cuenta en vez de crear otra."""
        self.otro.numero_telefono = "+5492235557788"
        self.otro.save()
        self.client.force_login(self.yo)
        self.client.post(self._url(), {
            "modo": "nuevo", "nombre": "Otro", "apellido": "Jugador",
            "telefono": "223 555-7788"})

        self.assertEqual(
            User.objects.filter(apellido="Jugador").count(), 1,
            "Se duplico un jugador que ya estaba en la app")
        equipo = Equipo.objects.filter(esta_activo=True).first()
        self.assertIn(self.otro.pk, (equipo.jugador1_id, equipo.jugador2_id))

    def test_no_se_anota_con_si_mismo(self):
        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": self.yo.pk})
        self.assertFalse(Inscripcion.objects.filter(torneo=self.torneo).exists())

    def test_respeta_los_cupos(self):
        self.torneo.cupos_totales = 1
        self.torneo.save()
        j1 = User.objects.create_user(email="c1@d.com", password="x", nombre="C", apellido="Uno", division=self.division)
        j2 = User.objects.create_user(email="c2@d.com", password="x", nombre="C", apellido="Dos", division=self.division)
        eq = Equipo.objects.create(jugador1=j1, jugador2=j2, division=self.division)
        Inscripcion.objects.create(torneo=self.torneo, equipo=eq)

        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": self.otro.pk})
        self.assertEqual(Inscripcion.objects.filter(torneo=self.torneo).count(), 1,
                         "Entro una inscripcion por encima del cupo")

    def test_no_deja_basura_si_falla(self):
        """Si la inscripcion falla, no queda el jugador recien creado colgado."""
        self.torneo.estado = Torneo.Estado.EN_JUEGO
        self.torneo.save()
        self.client.force_login(self.yo)
        self.client.post(self._url(), {
            "modo": "nuevo", "nombre": "Fantasma", "apellido": "Colgado",
            "telefono": "+5492235550000"})
        self.assertFalse(
            User.objects.filter(nombre="Fantasma").exists(),
            "Quedo un usuario huerfano de un intento fallido")

    def test_no_se_anota_si_ya_tiene_pareja(self):
        Equipo.objects.create(jugador1=self.yo, jugador2=self.otro, division=self.division)
        tercero = User.objects.create_user(
            email="ter@d.com", password="x", nombre="Ter", apellido="Cero", division=self.division)
        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": tercero.pk})
        self.assertFalse(Inscripcion.objects.filter(torneo=self.torneo).exists())

    def test_el_companero_puede_salirse(self):
        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": self.otro.pk})
        equipo = Equipo.objects.filter(esta_activo=True).first()

        self.client.force_login(self.otro)
        resp = self.client.post(
            reverse("torneos:salir_de_la_pareja", kwargs={"pk": equipo.pk}))
        self.assertIn(resp.status_code, (301, 302))

        equipo.refresh_from_db()
        self.assertFalse(equipo.esta_activo)
        self.assertFalse(
            Inscripcion.objects.filter(torneo=self.torneo).exists(),
            "Se deshizo la pareja pero quedo la inscripcion")

    def test_un_tercero_no_puede_deshacer_una_pareja_ajena(self):
        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": self.otro.pk})
        equipo = Equipo.objects.filter(esta_activo=True).first()

        ajeno = User.objects.create_user(
            email="aj@d.com", password="x", nombre="Aj", apellido="Eno", division=self.division)
        self.client.force_login(ajeno)
        resp = self.client.post(
            reverse("torneos:salir_de_la_pareja", kwargs={"pk": equipo.pk}))
        self.assertIn(resp.status_code, (403, 404))
        equipo.refresh_from_db()
        self.assertTrue(equipo.esta_activo)

    def test_no_se_puede_salir_con_el_torneo_ya_empezado(self):
        self.client.force_login(self.yo)
        self.client.post(self._url(), {"modo": "existente", "companero": self.otro.pk})
        equipo = Equipo.objects.filter(esta_activo=True).first()

        self.torneo.estado = Torneo.Estado.EN_JUEGO
        self.torneo.save()

        self.client.force_login(self.otro)
        self.client.post(reverse("torneos:salir_de_la_pareja", kwargs={"pk": equipo.pk}))
        equipo.refresh_from_db()
        self.assertTrue(
            equipo.esta_activo,
            "Se deshizo una pareja de un torneo que ya arranco")


@override_settings(STORAGES=TEST_STORAGES)
class ReproTelefonoPropioTests(TestCase):
    """Reproduce el caso reportado: el usuario prueba con SU PROPIO telefono."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgRep", alias="orgrep")
        self.torneo = Torneo.objects.create(
            nombre="Repro", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=7),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=3),
            cupos_totales=8, estado=Torneo.Estado.ABIERTO)
        self.yo = User.objects.create_user(
            email="yo@rep.com", password="x", nombre="Yo", apellido="Mismo",
            division=self.division, genero="MASCULINO")
        self.yo.numero_telefono = "+5492235551234"
        self.yo.save()

    def test_pongo_mi_propio_telefono(self):
        self.client.force_login(self.yo)
        resp = self.client.post(
            reverse("torneos:inscribirse_con_companero",
                    kwargs={"torneo_pk": self.torneo.pk}),
            {"modo": "nuevo", "nombre": "Yo", "apellido": "Mismo",
             "telefono": "+54 9 223 555-1234"})

        print("\n--- STATUS:", resp.status_code)
        if resp.status_code == 200:
            html = resp.content.decode()
            import re
            bloque = re.search(r'alert-error(.{0,600}?)</div>', html, re.S)
            if bloque:
                texto = re.sub(r'<[^>]+>', ' ', bloque.group(1))
                texto = ' '.join(texto.split())
                print("--- ERROR MOSTRADO:", texto[:250])
        print("--- inscripciones:", Inscripcion.objects.filter(torneo=self.torneo).count())
        print("--- usuarios creados de mas:", User.objects.filter(apellido="Mismo").count())


@override_settings(STORAGES=TEST_STORAGES)
class AltaSinCuentaTests(TestCase):
    """Anotarse a un torneo sin tener cuenta: crea las dos cuentas y la pareja."""

    def setUp(self):
        from accounts.models import Organizacion
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.org = Organizacion.objects.create(nombre="OrgAlta", alias="orgalta")
        self.torneo = Torneo.objects.create(
            nombre="Abierto Sin Cuenta", division=self.division, organizacion=self.org,
            fecha_inicio=timezone.now().date() + timedelta(days=7),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=3),
            cupos_totales=16, estado=Torneo.Estado.ABIERTO)

    def _datos(self, **extra):
        d = {
            "nombre": "Juan", "apellido": "Perez",
            "email": "juan@mail.com", "telefono": "+54 9 223 555-1111",
            "companero_tiene_cuenta": "no",
            "companero_nombre": "Pedro", "companero_apellido": "Gomez",
            "companero_email": "pedro@mail.com",
            "companero_telefono": "+54 9 223 555-2222",
            "division": self.division.pk,
        }
        d.update(extra)
        return d

    def test_crea_las_dos_cuentas_y_la_inscripcion(self):
        resp = self.client.post(
            reverse("torneos:inscribirse_sin_cuenta", kwargs={"torneo_pk": self.torneo.pk}),
            self._datos())
        self.assertIn(resp.status_code, (301, 302), getattr(resp, 'context', None) and resp.context.get('form').errors)

        juan = User.objects.get(email="juan@mail.com")
        pedro = User.objects.get(email="pedro@mail.com")
        self.assertTrue(juan.debe_cambiar_password)
        self.assertTrue(pedro.debe_cambiar_password)
        self.assertFalse(juan.is_dummy)
        self.assertEqual(self.torneo.inscripciones.count(), 1)
        equipo = self.torneo.inscripciones.first().equipo
        self.assertEqual({equipo.jugador1_id, equipo.jugador2_id}, {juan.pk, pedro.pk})

    def test_la_password_no_es_adivinable(self):
        from torneos.services.alta_sin_cuenta import generar_password
        p = generar_password("Juan")
        self.assertTrue(p.startswith("juan"))
        self.assertNotEqual(p, "juan123")
        self.assertRegex(p, r"^juan\d{4}$")
        # Dos llamadas seguidas no dan lo mismo
        self.assertNotEqual(generar_password("Juan"), generar_password("Juan"))

    def test_engancha_al_jugador_que_cargo_el_organizador(self):
        """Si el organizador ya lo habia cargado, se reusa ESA cuenta con su historial."""
        dummy = User.objects.create_user(
            email="dummy_x@padel.local", password="x", nombre="Pedro", apellido="Gomez",
            division=self.division)
        dummy.is_dummy = True
        dummy.numero_telefono = "2235552222"
        dummy.is_active = False
        dummy.save()

        antes = User.objects.count()
        self.client.post(
            reverse("torneos:inscribirse_sin_cuenta", kwargs={"torneo_pk": self.torneo.pk}),
            self._datos())

        dummy.refresh_from_db()
        self.assertFalse(dummy.is_dummy, "Deberia haber dejado de ser dummy")
        self.assertTrue(dummy.is_active)
        self.assertEqual(dummy.email, "pedro@mail.com")
        # Solo se creo el que faltaba (Juan), no un Pedro duplicado
        self.assertEqual(User.objects.count(), antes + 1)

    def test_no_permite_mismo_email_para_los_dos(self):
        resp = self.client.post(
            reverse("torneos:inscribirse_sin_cuenta", kwargs={"torneo_pk": self.torneo.pk}),
            self._datos(companero_email="juan@mail.com"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "mismo email")

    def test_no_deja_anotarse_si_el_torneo_esta_cerrado(self):
        self.torneo.estado = Torneo.Estado.EN_JUEGO
        self.torneo.save()
        resp = self.client.post(
            reverse("torneos:inscribirse_sin_cuenta", kwargs={"torneo_pk": self.torneo.pk}),
            self._datos())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.torneo.inscripciones.count(), 0)

    def test_el_middleware_obliga_a_cambiar_la_password(self):
        self.client.post(
            reverse("torneos:inscribirse_sin_cuenta", kwargs={"torneo_pk": self.torneo.pk}),
            self._datos())
        juan = User.objects.get(email="juan@mail.com")
        self.client.force_login(juan)
        resp = self.client.get(reverse("core:home"))
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn("cambiar-password", resp["Location"])

    def test_despues_de_cambiarla_puede_navegar(self):
        self.client.post(
            reverse("torneos:inscribirse_sin_cuenta", kwargs={"torneo_pk": self.torneo.pk}),
            self._datos())
        juan = User.objects.get(email="juan@mail.com")
        self.client.force_login(juan)
        self.client.post(reverse("accounts:cambiar_password"), {
            "new_password1": "UnaClaveLarga123", "new_password2": "UnaClaveLarga123"})
        juan.refresh_from_db()
        self.assertFalse(juan.debe_cambiar_password)
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_el_mensaje_de_whatsapp_trae_los_datos_de_acceso(self):
        from torneos.services.alta_sin_cuenta import mensaje_bienvenida
        u = User.objects.create_user(email="p@m.com", password="x", nombre="Pedro", apellido="G")
        msg = mensaje_bienvenida(u, "pedro4821", self.torneo)
        self.assertIn("Ya tenés tu cuenta", msg)
        self.assertIn("p@m.com", msg)
        self.assertIn("pedro4821", msg)
        self.assertIn(self.torneo.nombre, msg)
