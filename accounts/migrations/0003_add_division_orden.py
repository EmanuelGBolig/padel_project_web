# Generated migration for adding orden field to Division model

from django.db import migrations, models


def populate_orden(apps, schema_editor):
    """Populate orden field for existing divisions"""
    Division = apps.get_model('accounts', 'Division')
    
    # Mapeo de nombres a números de orden (Octava=8 hasta Primera=1)
    orden_map = {
        'Primera': 1, '1ra': 1, '1a': 1,
        'Segunda': 2, '2da': 2, '2a': 2,
        'Tercera': 3, '3ra': 3, '3a': 3,
        'Cuarta': 4, '4ta': 4, '4a': 4,
        'Quinta': 5, '5ta': 5, '5a': 5,
        'Sexta': 6, '6ta': 6, '6a': 6,
        'Séptima': 7, '7ma': 7, '7a': 7,
        'Septima': 7,  # Sin tilde
        'Octava': 8, '8va': 8, '8a': 8,
    }
    
    # Tracking de números usados para garantizar uniqueness
    used_ordenes = set()
    fallback_orden_counter = 100
    
    for division in Division.objects.all():
        # Buscar el orden basado en el nombre
        orden = orden_map.get(division.nombre, None)
        
        # Si no se encuentra, intentar quitar espacios y normalizar
        if orden is None:
            normalized = division.nombre.strip().replace(' ', '')
            orden = orden_map.get(normalized, None)
        
        # Si el orden ya está usado, necesitamos un fallback
        if orden in used_ordenes:
            orden = fallback_orden_counter
            fallback_orden_counter += 1
        
        # Si aún no se encuentra, asignar un número alto secuencial
        if orden is None:
            orden = fallback_orden_counter
            fallback_orden_counter += 1
        
        used_ordenes.add(orden)
        division.orden = orden
        division.save()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_customuser_options'),
    ]

    operations = [
        # 1. Agregar campo orden con default temporal para evitar errores
        migrations.AddField(
            model_name='division',
            name='orden',
            field=models.PositiveSmallIntegerField(
                default=999,
                help_text='Octava=8, Séptima=7, ..., Primera=1'
            ),
        ),
        # 2. Poblar valores correctos
        migrations.RunPython(populate_orden, reverse_code=migrations.RunPython.noop),
        # 3. Hacer el campo unique
        migrations.AlterField(
            model_name='division',
            name='orden',
            field=models.PositiveSmallIntegerField(
                unique=True,
                help_text='Octava=8, Séptima=7, ..., Primera=1'
            ),
        ),
        # 4. Agregar Meta class para ordering
        migrations.AlterModelOptions(
            name='division',
            options={
                'ordering': ['orden'],
                'verbose_name_plural': 'Divisiones'
            },
        ),
    ]
