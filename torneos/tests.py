from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Division
from equipos.models import Equipo
from .models import Torneo, Inscripcion, Grupo, EquipoGrupo, PartidoGrupo

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
        self.assertIn("http://testserver/static/img/og-image.jpg", html)

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

    def test_zona_completa_llena_slots(self):
        self._generar_bracket()
        from .models import Partido
        p1a = Partido.objects.get(torneo=self.torneo, placeholder_e1="1A")
        p2a = Partido.objects.get(torneo=self.torneo, placeholder_e2="2A")
        self.assertIsNotNone(p1a.equipo1, "1A debería estar lleno (Zona A cerrada)")
        self.assertIsNotNone(p2a.equipo2, "2A debería estar lleno (Zona A cerrada)")

    def test_zona_incompleta_queda_placeholder(self):
        self._generar_bracket()
        from .models import Partido
        # 2B y 1B pertenecen a la Zona B (incompleta) -> NO deben tener equipo.
        p2b = Partido.objects.get(torneo=self.torneo, placeholder_e2="2B")
        p1b = Partido.objects.get(torneo=self.torneo, placeholder_e1="1B")
        self.assertIsNone(p2b.equipo2, "2B NO debe estar lleno: la Zona B no terminó")
        self.assertIsNone(p1b.equipo1, "1B NO debe estar lleno: la Zona B no terminó")


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
