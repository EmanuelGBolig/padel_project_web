"""
Management command para medir el rendimiento de la página de rankings
"""
from django.core.management.base import BaseCommand
from django.test.utils import override_settings
from django.db import connection, reset_queries
import time


class Command(BaseCommand):
    help = 'Mide el rendimiento de la vista de rankings'

    def handle(self, *args, **options):
        from equipos.views import RankingListView
        from django.test import RequestFactory
        from django.contrib.auth import get_user_model
        from django.core.cache import cache
        
        User = get_user_model()
        factory = RequestFactory()
        
        self.stdout.write(self.style.SUCCESS('\n=== Test de Rendimiento - Rankings ===\n'))
        
        # Limpiar cache antes de la prueba
        cache.clear()
        self.stdout.write('Cache limpiado')
        
        # Test 1: Primera carga (sin cache)
        self.stdout.write(self.style.WARNING('\n1. Primera carga (sin cache):'))
        request = factory.get('/equipos/rankings/')
        request.user = User.objects.first() if User.objects.exists() else None
        
        reset_queries()
        start_time = time.time()
        
        view = RankingListView()
        view.request = request
        queryset = view.get_queryset()
        
        end_time = time.time()
        query_count = len(connection.queries)
        
        self.stdout.write(f'  ⏱️  Tiempo: {(end_time - start_time)*1000:.2f}ms')
        self.stdout.write(f'  🔢 Queries: {query_count}')
        self.stdout.write(f'  📊 Divisiones: {len(queryset)}')
        
        # Test 2: Segunda carga (con cache)
        self.stdout.write(self.style.WARNING('\n2. Segunda carga (con cache):'))
        request2 = factory.get('/equipos/rankings/')
        request2.user = request.user
        
        reset_queries()
        start_time = time.time()
        
        view2 = RankingListView()
        view2.request = request2
        queryset2 = view2.get_queryset()
        
        end_time = time.time()
        query_count2 = len(connection.queries)
        
        self.stdout.write(f'  ⏱️  Tiempo: {(end_time - start_time)*1000:.2f}ms')
        self.stdout.write(f'  🔢 Queries: {query_count2}')
        self.stdout.write(f'  📊 Divisiones: {len(queryset2)}')
        
        # Test 3: Filtrado por división
        from equipos.models import Division
        if Division.objects.exists():
            division = Division.objects.first()
            self.stdout.write(self.style.WARNING(f'\n3. Filtrado por división "{division.nombre}":'))
            request3 = factory.get(f'/equipos/rankings/?division={division.id}')
            request3.user = request.user
            
            reset_queries()
            start_time = time.time()
            
            view3 = RankingListView()
            view3.request = request3
            queryset3 = view3.get_queryset()
            
            end_time = time.time()
            query_count3 = len(connection.queries)
            
            self.stdout.write(f'  ⏱️  Tiempo: {(end_time - start_time)*1000:.2f}ms')
            self.stdout.write(f'  🔢 Queries: {query_count3}')
            self.stdout.write(f'  📊 Equipos: {len(queryset3[0]["equipos"]) if queryset3 else 0}')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Test completado\n'))
