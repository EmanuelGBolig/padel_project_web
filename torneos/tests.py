from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Division
from equipos.models import Equipo
from .models import Torneo, Inscripcion, Grupo, EquipoGrupo, PartidoGrupo

# En tests no hay manifest de WhiteNoise (no se corre collectstatic): usamos el
# storage estático plano para que {% static %} no falle al renderizar.
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

User = get_user_model()


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
