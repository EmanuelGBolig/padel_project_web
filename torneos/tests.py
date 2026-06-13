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


class DescribirEstructuraTests(TestCase):
    """TP-17.3: proyección de estructura para la vista previa del alta."""

    def test_grupos_con_formato_optimizado(self):
        from .formats import describir_estructura
        for n, num_zonas in [(6, 2), (8, 2), (12, 4), (13, 4), (16, 5), (17, 6), (24, 8)]:
            r = describir_estructura(n, 'G')
            self.assertTrue(r['ok'], f"n={n} debería ser ok")
            self.assertEqual(r['nivel'], 'ok')
            self.assertEqual(len(r['zonas']), num_zonas, f"n={n}")

    def test_grupos_sin_formato_optimizado_igual_genera(self):
        # 20/22/23 no tienen formato en FORMATS pero el sistema arma zonas genéricas.
        from .formats import describir_estructura
        for n in (20, 22, 23):
            r = describir_estructura(n, 'G')
            self.assertTrue(r['ok'], f"n={n}")
            self.assertEqual(r['nivel'], 'ok')
            self.assertTrue(r['zonas'])

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
