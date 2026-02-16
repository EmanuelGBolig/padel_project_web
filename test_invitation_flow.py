import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from equipos.models import Equipo, Invitation
from accounts.models import Division

User = get_user_model()

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

def test_invitation_flow():
    print("--- Starting Invitation Flow Test ---")
    
    # 1. Setup Data
    div, _ = Division.objects.get_or_create(nombre="TestDiv", orden=99)
    
    print(f"Division created: {div.id}, {div.nombre}")
    
    try:
        # Try explicit create if get_or_create fails or just to be sure
        if User.objects.filter(email="u1@test.com").exists():
            u1 = User.objects.get(email="u1@test.com")
            print(f"User u1 exists: {u1.id}, div: {u1.division_id}")
            if not u1.division:
                print("Setting division for u1...")
                u1.division = div
                u1.save()
        else:
            print("Creating u1...")
            u1 = User.objects.create(email="u1@test.com", nombre='User1', apellido='Test', division=div)
            u1.set_password('pass')
            u1.save()
            
        if User.objects.filter(email="u2@test.com").exists():
            u2 = User.objects.get(email="u2@test.com")
            print(f"User u2 exists: {u2.id}, div: {u2.division_id}")
            if not u2.division:
                print("Setting division for u2...")
                u2.division = div
                u2.save()
        else:
            print("Creating u2...")
            u2 = User.objects.create(email="u2@test.com", nombre='User2', apellido='Test', division=div)
            u2.set_password('pass')
            u2.save()
            
    except Exception as e:
        print(f"ERROR creating/getting users: {e}")
        raise e
    
    # Clean previous data
    cleanup(u1, u2)
    
    print(f"Users created: {u1.email}, {u2.email}")
    
    # 2. User 1 invites User 2
    print("\n[Step 1] User 1 invites User 2")
    invitation = Invitation.objects.create(inviter=u1, invited=u2, status=Invitation.Status.PENDING)
    print(f"Invitation created: {invitation}")
    
    # Check assertions
    assert Invitation.objects.filter(inviter=u1, invited=u2, status='PENDING').exists()
    assert not Equipo.objects.filter(jugador1=u1).exists()
    assert not Equipo.objects.filter(jugador2=u2).exists()
    print("-> Assertion Passed: Invitation pending, no team yet.")
    
    # 3. User 2 accepts
    print("\n[Step 2] User 2 accepts invitation")
    # Simulate view logic
    Equipo.objects.create(jugador1=invitation.inviter, jugador2=invitation.invited, division=invitation.inviter.division)
    invitation.status = Invitation.Status.ACCEPTED
    invitation.save()
    
    # Check assertions
    team = Equipo.objects.filter(jugador1=u1, jugador2=u2).first()
    assert team is not None
    assert invitation.status == 'ACCEPTED'
    print(f"-> Assertion Passed: Team created ({team}), invitation accepted.")
    
    # Cleanup
    cleanup(u1, u2)
    print("\n--- Test Completed Successfully ---")

def cleanup(u1, u2):
    Invitation.objects.filter(inviter=u1).delete()
    Invitation.objects.filter(invited=u1).delete()
    Invitation.objects.filter(inviter=u2).delete()
    Invitation.objects.filter(invited=u2).delete()
    Equipo.objects.filter(jugador1=u1).delete()
    Equipo.objects.filter(jugador2=u1).delete()
    Equipo.objects.filter(jugador1=u2).delete()
    Equipo.objects.filter(jugador2=u2).delete()

if __name__ == "__main__":
    test_invitation_flow()
