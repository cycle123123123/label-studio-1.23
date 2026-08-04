from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0034_project_annotator_evaluation_enabled'),
        ('tasks', '0060_add_allow_skip_to_task'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Creation time', verbose_name='created at')),
                ('task', models.OneToOneField(help_text='Assigned task', on_delete=django.db.models.deletion.CASCADE, related_name='assignment', to='tasks.task')),
                ('user', models.ForeignKey(help_text='Assigned user', on_delete=django.db.models.deletion.CASCADE, related_name='task_assignments', to=settings.AUTH_USER_MODEL)),
                ('assigned_by', models.ForeignKey(blank=True, help_text='User who assigned the task', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_task_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'task_assignment',
            },
        ),
        migrations.CreateModel(
            name='TaskAssignmentAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('assigned', 'Assigned'), ('reassigned', 'Reassigned'), ('unassigned', 'Unassigned')], help_text='Assignment action type', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Creation time', verbose_name='created at')),
                ('project', models.ForeignKey(help_text='Project of assignment action', on_delete=django.db.models.deletion.CASCADE, related_name='task_assignment_audit_logs', to='projects.project')),
                ('task', models.ForeignKey(help_text='Task affected by assignment action', on_delete=django.db.models.deletion.CASCADE, related_name='assignment_audit_logs', to='tasks.task')),
                ('assignee', models.ForeignKey(blank=True, help_text='Current assignee after action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_assignment_audit_as_assignee', to=settings.AUTH_USER_MODEL)),
                ('previous_assignee', models.ForeignKey(blank=True, help_text='Assignee before action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_assignment_audit_as_previous_assignee', to=settings.AUTH_USER_MODEL)),
                ('assigned_by', models.ForeignKey(blank=True, help_text='User who performed assignment action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_assignment_audit_as_actor', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'task_assignment_audit_log',
            },
        ),
        migrations.CreateModel(
            name='TaskWorkflowAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('submitted', 'Submitted'), ('skipped', 'Skipped')], help_text='Workflow action type', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Creation time', verbose_name='created at')),
                ('project', models.ForeignKey(help_text='Project of workflow action', on_delete=django.db.models.deletion.CASCADE, related_name='task_workflow_audit_logs', to='projects.project')),
                ('task', models.ForeignKey(help_text='Task affected by workflow action', on_delete=django.db.models.deletion.CASCADE, related_name='workflow_audit_logs', to='tasks.task')),
                ('annotation', models.ForeignKey(blank=True, help_text='Annotation associated with workflow action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='workflow_audit_logs', to='tasks.annotation')),
                ('actor', models.ForeignKey(blank=True, help_text='User who performed workflow action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='task_workflow_audit_as_actor', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'task_workflow_audit_log',
            },
        ),
        migrations.AddIndex(
            model_name='taskassignment',
            index=models.Index(fields=['user', 'task'], name='task_assign_user_iddx'),
        ),
        migrations.AddIndex(
            model_name='taskassignment',
            index=models.Index(fields=['task', 'user'], name='task_assign_task_iddx'),
        ),
        migrations.AddIndex(
            model_name='taskassignmentauditlog',
            index=models.Index(fields=['project', '-created_at'], name='task_assignm_proj_idx'),
        ),
        migrations.AddIndex(
            model_name='taskassignmentauditlog',
            index=models.Index(fields=['task', '-created_at'], name='task_assignm_task_idx'),
        ),
        migrations.AddIndex(
            model_name='taskassignmentauditlog',
            index=models.Index(fields=['assignee', '-created_at'], name='task_assignm_assign_idx'),
        ),
        migrations.AddIndex(
            model_name='taskworkflowauditlog',
            index=models.Index(fields=['project', '-created_at'], name='task_workflo_proj_idx'),
        ),
        migrations.AddIndex(
            model_name='taskworkflowauditlog',
            index=models.Index(fields=['task', '-created_at'], name='task_workflo_task_idx'),
        ),
        migrations.AddIndex(
            model_name='taskworkflowauditlog',
            index=models.Index(fields=['actor', '-created_at'], name='task_workflo_actor_idx'),
        ),
    ]
