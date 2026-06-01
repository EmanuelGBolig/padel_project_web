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


@override_settings(STORAGES=TEST_STORAGES)
class FichaLogrosCompletitudTests(TestCase):
    """TP-19.3/.4: ficha de jugador, logros, racha y medidor de perfil."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Quinta", orden=5)
        self.user = User.objects.create_user(
            email="ficha@t.com", password="x", nombre="Caro", apellido="Lopez",
            genero="FEMENINO", division=self.division)

    def _form_data(self, **over):
        data = {
            'email': self.user.email, 'nombre': 'Caro', 'apellido': 'Lopez',
            'genero': 'FEMENINO', 'division': self.division.pk,
            'numero_telefono': '',
            'posicion_cancha': 'R', 'mano_habil': 'D', 'club': 'AprendePadel',
            'ciudad': 'Mar del Plata', 'juega_desde': 2019, 'instagram': '@caro.padel',
            'bio': 'Me gusta el revés.',
        }
        data.update(over)
        return data

    def test_instagram_se_normaliza(self):
        from accounts.forms import CustomUserProfileForm
        f = CustomUserProfileForm(data=self._form_data(instagram='@caro.padel'), instance=self.user)
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data['instagram'], 'caro.padel')
        f2 = CustomUserProfileForm(data=self._form_data(instagram='https://instagram.com/caro.padel?x=1'), instance=self.user)
        self.assertTrue(f2.is_valid(), f2.errors)
        self.assertEqual(f2.cleaned_data['instagram'], 'caro.padel')

    def test_juega_desde_fuera_de_rango_invalida(self):
        from accounts.forms import CustomUserProfileForm
        f = CustomUserProfileForm(data=self._form_data(juega_desde=1800), instance=self.user)
        self.assertFalse(f.is_valid())
        self.assertIn('juega_desde', f.errors)

    def test_achievements_campeon_desbloqueado(self):
        from accounts.utils import get_player_achievements
        stats = {'partidos_jugados': 12, 'torneos_ganados': 1, 'win_rate': 70, 'racha_maxima': 4}
        ach = get_player_achievements(self.user, stats)
        by_title = {a['titulo']: a for a in ach}
        self.assertTrue(by_title['Campeón']['unlocked'])
        self.assertTrue(by_title['+10 partidos']['unlocked'])
        self.assertFalse(by_title['Top 10']['unlocked'])  # bloqueado (sin histórico)

    def test_completitud_sube_con_datos(self):
        from accounts.utils import get_profile_completeness
        base = get_profile_completeness(self.user)['pct']
        self.user.ciudad = "MDQ"
        self.user.instagram = "caro"
        self.user.save()
        despues = get_profile_completeness(self.user)['pct']
        self.assertGreater(despues, base)

    def test_perfil_propio_muestra_ficha_y_medidor(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('accounts:perfil')).content.decode()
        self.assertIn('Mi juego', html)
        self.assertIn('Tu perfil está al', html)
        self.assertIn('Logros', html)

    def test_perfil_publico_muestra_ficha_cargada(self):
        self.user.posicion_cancha = 'R'
        self.user.ciudad = 'Mar del Plata'
        self.user.save()
        url = reverse('accounts:detalle', kwargs={'pk': self.user.pk})
        html = self.client.get(url).content.decode()
        self.assertIn('Mi juego', html)
        self.assertIn('Mar del Plata', html)


@override_settings(STORAGES=TEST_STORAGES)
class DedupCuentasTests(TestCase):
    """TP-20 (etapa 1): detección de duplicados + merge real→real + exclusión de ranking."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.division = Division.objects.create(nombre="Cuarta", orden=4)

    def _player(self, email, nombre, apellido, dummy=False):
        return User.objects.create_user(
            email=email, password="x", nombre=nombre, apellido=apellido,
            genero="MASCULINO", division=self.division, is_dummy=dummy)

    def test_detecta_variantes_de_nombre(self):
        from accounts.utils import find_duplicate_candidates
        a = self._player("a@t.com", "Juan", "Pérez")     # con tilde
        b = self._player("b@t.com", "Juan", "Perez")     # sin tilde -> misma clave
        c = self._player("c@t.com", "Juan", "Peres")     # typo -> similar
        self._player("z@t.com", "María", "López")        # distinta, no agrupa
        grupos = find_duplicate_candidates()
        ids_en_grupos = [{u.id for u in g['usuarios']} for g in grupos]
        # Existe un grupo que contiene a los tres Juan
        self.assertTrue(any({a.id, b.id, c.id} <= s for s in ids_en_grupos))
        # María no aparece agrupada con los Juan
        self.assertFalse(any(self._maria_id in s and a.id in s for s in ids_en_grupos))

    @property
    def _maria_id(self):
        return User.objects.get(email="z@t.com").id

    def test_merge_real_desactiva_y_enlaza(self):
        from accounts.utils import merge_users
        from equipos.models import Equipo
        p1 = self._player("p1@t.com", "Leo", "Gómez")
        p2 = self._player("p2@t.com", "Leo", "Gomez")
        compa = self._player("co@t.com", "Compa", "Uno")
        eq = Equipo.objects.create(jugador1=p2, jugador2=compa, division=self.division)
        merge_users(p2, p1)
        p2.refresh_from_db()
        self.assertFalse(p2.is_active)
        self.assertEqual(p2.merged_into_id, p1.id)
        # El equipo pasó a p1
        eq.refresh_from_db()
        self.assertEqual(eq.jugador1_id, p1.id)
        # p1 sigue activo
        p1.refresh_from_db()
        self.assertTrue(p1.is_active)

    def test_merge_no_permite_destino_dummy(self):
        from accounts.utils import merge_users
        real = self._player("r@t.com", "Ana", "Sosa")
        dummy = self._player("d@t.com", "Ana", "Sosa", dummy=True)
        with self.assertRaises(ValueError):
            merge_users(real, dummy)

    def test_ranking_excluye_fusionadas(self):
        from accounts.utils import merge_users, get_division_rankings
        from django.core.cache import cache
        p1 = self._player("rp1@t.com", "Eva", "Diaz")
        p2 = self._player("rp2@t.com", "Eva", "Diaz")
        cache.clear()
        ids_antes = {x['jugador'].id for x in get_division_rankings(self.division, force_recalc=True)}
        self.assertIn(p2.id, ids_antes)
        merge_users(p2, p1)
        cache.clear()
        ids_despues = {x['jugador'].id for x in get_division_rankings(self.division, force_recalc=True)}
        self.assertNotIn(p2.id, ids_despues)
        self.assertIn(p1.id, ids_despues)

    def test_vista_duplicados_admin(self):
        admin = User.objects.create_user(
            email="adm@t.com", password="x", nombre="Adm", apellido="In",
            genero="OTRO", tipo_usuario="ADMIN", is_staff=True)
        self.client.force_login(admin)
        resp = self.client.get(reverse('accounts:duplicados'))
        self.assertEqual(resp.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class MultiLoginCuentasFusionadasTests(TestCase):
    """TP-20 (etapa 2): entrar con cualquier mail de una persona cuyas cuentas se unificaron."""

    def setUp(self):
        self.division = Division.objects.create(nombre="Tercera", orden=3)
        self.p1 = User.objects.create_user(
            email="canon@t.com", password="secret1", nombre="Leo", apellido="Gómez",
            genero="MASCULINO", division=self.division)
        self.p2 = User.objects.create_user(
            email="vieja@t.com", password="secret2", nombre="Leo", apellido="Gomez",
            genero="MASCULINO", division=self.division)
        # Simular fusión p2 -> p1 (sin mover historial, alcanza para probar el backend)
        self.p2.merged_into = self.p1
        self.p2.is_active = False
        self.p2.save(update_fields=['merged_into', 'is_active'])

    def test_login_con_mail_viejo_y_pass_canonica(self):
        from django.contrib.auth import authenticate
        u = authenticate(None, username="vieja@t.com", password="secret1")
        self.assertIsNotNone(u)
        self.assertEqual(u.pk, self.p1.pk)

    def test_login_con_mail_viejo_y_pass_vieja_falla(self):
        from django.contrib.auth import authenticate
        self.assertIsNone(authenticate(None, username="vieja@t.com", password="secret2"))

    def test_login_normal_canonica_sigue_andando(self):
        from django.contrib.auth import authenticate
        u = authenticate(None, username="canon@t.com", password="secret1")
        self.assertEqual(u.pk, self.p1.pk)

    def test_cadena_de_fusiones(self):
        from django.contrib.auth import authenticate
        p3 = User.objects.create_user(
            email="masvieja@t.com", password="secret3", nombre="Leo", apellido="G",
            genero="MASCULINO", division=self.division)
        p3.merged_into = self.p2  # p3 -> p2 -> p1
        p3.is_active = False
        p3.save(update_fields=['merged_into', 'is_active'])
        u = authenticate(None, username="masvieja@t.com", password="secret1")
        self.assertEqual(u.pk, self.p1.pk)

    def test_client_login_con_cualquier_mail(self):
        self.assertTrue(self.client.login(username="vieja@t.com", password="secret1"))
        self.client.logout()
        self.assertFalse(self.client.login(username="vieja@t.com", password="secret2"))
