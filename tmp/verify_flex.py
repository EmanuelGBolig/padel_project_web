from accounts.models import CustomUser, Division
from equipos.models import Equipo
from torneos.models import Torneo
from torneos.views import TorneoDetailView
from django.utils import timezone
import datetime

def run_test():
    now = timezone.now()
    # Ensure divisions exist
    d3, _ = Division.objects.get_or_create(nombre='Tercera', defaults={'orden': 3})
    d4, _ = Division.objects.get_or_create(nombre='Cuarta', defaults={'orden': 4})
    d5, _ = Division.objects.get_or_create(nombre='Quinta', defaults={'orden': 5})
    d6, _ = Division.objects.get_or_create(nombre='Sexta', defaults={'orden': 6})

    # Ensure players exist
    u4, _ = CustomUser.objects.get_or_create(email='test4@example.com', defaults={'nombre': 't4', 'apellido': 't4', 'division': d4, 'tipo_usuario': 'PLAYER'})
    u6, _ = CustomUser.objects.get_or_create(email='test6@example.com', defaults={'nombre': 't6', 'apellido': 't6', 'division': d6, 'tipo_usuario': 'PLAYER'})
    
    # Update to ensure they have the right division for the test
    u4.division = d4; u4.save()
    u6.division = d6; u6.save()

    # Clean existing teams for these players to avoid UNIQUE constraints
    Equipo.objects.filter(jugador1=u4).delete()
    Equipo.objects.filter(jugador2=u4).delete()
    Equipo.objects.filter(jugador1=u6).delete()
    Equipo.objects.filter(jugador2=u6).delete()
    Equipo.objects.filter(nombre='TestPair').delete()

    # Create mixed team
    team = Equipo(jugador1=u4, jugador2=u6, nombre='TestPair')
    team.save()

    print(f"Team created: {team.nombre} (Divs: {u4.division.orden}, {u6.division.orden}) -> Assigned Team Div: {team.division.orden}")

    view = TorneoDetailView()

    def get_t(name, div):
        t = Torneo.objects.filter(nombre=name).first()
        if not t:
            t = Torneo.objects.create(nombre=name, division=div, fecha_inicio=now, fecha_limite_inscripcion=now, cupos_totales=20)
        return t

    t3 = get_t('T3', d3)
    t4 = get_t('T4', d4)
    t5 = get_t('T5', d5)
    t6 = get_t('T6', d6)
    tl = get_t('TL', None)

    print(f"T3 (Exp: False): {view._es_division_permitida(team, t3)}")
    print(f"T4 (Exp: True): {view._es_division_permitida(team, t4)}")
    print(f"T5 (Exp: True): {view._es_division_permitida(team, t5)}")
    print(f"T6 (Exp: True): {view._es_division_permitida(team, t6)}")
    print(f"TL (Exp: True): {view._es_division_permitida(team, tl)}")

if __name__ == '__main__':
    run_test()
