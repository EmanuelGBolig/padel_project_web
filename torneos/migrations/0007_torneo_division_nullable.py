# Generated migration for making division nullable in Torneo model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('torneos', '0006_partido_fecha_hora_partidogrupo_fecha_hora_and_more'),
        ('accounts', '0003_add_division_orden'),  # Depends on division having orden field
    ]

    operations = [
        migrations.AlterField(
            model_name='torneo',
            name='division',
            field=models.ForeignKey(
                blank=True,
                help_text='Dejar vacío para torneos libres (cualquier división)',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='accounts.division'
            ),
        ),
    ]
