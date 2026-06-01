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


@override_settings(STORAGES=TEST_STORAGES)
class PerfilStatsHistorialTests(TestCase):
    """TP-19.1/.2: stats completas + resultados recientes (con W.O.)."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from django.core.cache import cache
        from equipos.models import Equipo
        from torneos.models import Torneo, Grupo, PartidoGrupo
        cache.clear()
        self.division = Division.objects.create(nombre="Sexta", orden=6)
        self.p = User.objects.create_user(email="p19@t.com", password="x",
                                           nombre="Ana", apellido="Gómez", division=self.division)
        compa = User.objects.create_user(email="c19@t.com", password="x",
                                          nombre="Bea", apellido="Ruiz", division=self.division)
        r1 = User.objects.create_user(email="r1_19@t.com", password="x",
                                      nombre="Rosa", apellido="Uno", division=self.division)
        r2 = User.objects.create_user(email="r2_19@t.com", password="x",
                                      nombre="Rita", apellido="Dos", division=self.division)
        self.mi_equipo = Equipo.objects.create(jugador1=self.p, jugador2=compa, division=self.division)
        rival = Equipo.objects.create(jugador1=r1, jugador2=r2, division=self.division)
        self.torneo = Torneo.objects.create(
            nombre="Copa Test", division=self.division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=1), estado='EJ')
        grupo = Grupo.objects.create(torneo=self.torneo, nombre="Zona A")
        # Victoria normal
        PartidoGrupo.objects.create(
            grupo=grupo, equipo1=self.mi_equipo, equipo2=rival,
            e1_set1=6, e2_set1=2, e1_set2=6, e2_set2=3,
            e1_sets_ganados=2, e2_sets_ganados=0,
            e1_games_ganados=12, e2_games_ganados=5, ganador=self.mi_equipo)
        # W.O. a favor
        PartidoGrupo.objects.create(
            grupo=grupo, equipo1=self.mi_equipo, equipo2=rival,
            e1_sets_ganados=2, e2_sets_ganados=0, ganador=self.mi_equipo, resolucion='W')

    def test_stats_incluye_resultados_recientes_con_wo(self):
        from accounts.utils import get_player_stats
        from django.core.cache import cache
        cache.delete(f'player_stats_{self.p.id}')
        stats = get_player_stats(self.p)
        self.assertEqual(stats['victorias'], 2)
        self.assertEqual(stats['derrotas'], 0)
        self.assertGreaterEqual(len(stats['resultados_recientes']), 2)
        etiquetas = [r['etiqueta'] for r in stats['resultados_recientes']]
        self.assertIn('W.O.', etiquetas)
        self.assertTrue(all(r['gano'] for r in stats['resultados_recientes']))

    def test_perfil_publico_muestra_stats_completas(self):
        url = reverse('accounts:detalle', kwargs={'pk': self.p.id})
        html = self.client.get(url).content.decode()
        for needle in ['Derrotas', 'Win rate', 'Títulos', 'Resultados recientes']:
            self.assertIn(needle, html)

    def test_perfil_propio_render(self):
        self.client.force_login(self.p)
        html = self.client.get(reverse('accounts:perfil')).content.decode()
        for needle in ['Derrotas', 'Win rate', 'Resultados recientes',
                       'Victorias temporada', 'Torneos jugados']:
            self.assertIn(needle, html)
