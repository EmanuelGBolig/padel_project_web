TEST = '''

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

        print("\\n--- STATUS:", resp.status_code)
        if resp.status_code == 200:
            html = resp.content.decode()
            import re
            for m in re.finditer(r'alert-error.*?</div>', html, re.S):
                print("--- ERROR MOSTRADO:", re.sub(r'<[^>]+>', ' ', m.group(0)).strip()[:200])
        print("--- inscripciones:", Inscripcion.objects.filter(torneo=self.torneo).count())
        print("--- usuarios creados de mas:", User.objects.filter(apellido="Mismo").count())
'''

with open('torneos/tests.py', 'a', encoding='utf-8', newline='\n') as f:
    f.write(TEST)
print("test de reproduccion agregado")
