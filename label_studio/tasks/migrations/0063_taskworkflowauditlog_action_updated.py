# Generated manually for ACTION_UPDATED support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0062_task_assignment_model_fixes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='taskworkflowauditlog',
            name='action',
            field=models.CharField(
                choices=[('submitted', 'Submitted'), ('skipped', 'Skipped'), ('updated', 'Updated')],
                help_text='Workflow action type',
                max_length=32,
            ),
        ),
    ]
