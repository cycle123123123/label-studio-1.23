"""Reassign a list of tasks from one user to another (single-annotator transfer).

Reads task ids from a CSV (column `task_id`), shows current state, and applies the
assignment change through `tasks.assignment.apply_task_assignments`, so audit logs
are written and re-running is idempotent.

用法（服务器上，app 容器内）：

  docker compose exec -T app python manage.py shell < /tmp/reassign_tasks.py

参数在文件顶部 CONFIG 区；APPLY=False 时只打印核对结果，不写库。
"""

import csv

from django.contrib.auth import get_user_model

from projects.models import Project
from tasks.assignment import apply_task_assignments
from tasks.models import AnnotationDraft, TaskAssignment

# ---------------- CONFIG ----------------
PROJECT_ID = 1
CSV_PATH = '/tmp/transfer_tasks.csv'   # 单列 task_id
FROM_EMAIL = '1@163.com'               # 齐添乐
TO_EMAIL = '3@163.com'                 # 孙无双
ACTOR_EMAIL = '13243186667'            # 执行人（管理员）
APPLY = False                          # True 才真正写库
# ----------------------------------------

User = get_user_model()
project = Project.objects.get(pk=PROJECT_ID)
src = User.objects.get(email=FROM_EMAIL)
dst = User.objects.get(email=TO_EMAIL)
actor = User.objects.get(email=ACTOR_EMAIL)

with open(CSV_PATH, newline='', encoding='utf-8-sig') as fh:
    task_ids = sorted({int(r['task_id']) for r in csv.DictReader(fh) if r.get('task_id')})

owner_map = {}
for row in TaskAssignment.objects.filter(task_id__in=task_ids).values('task_id', 'user__email'):
    owner_map.setdefault(row['task_id'], set()).add(row['user__email'])

lost = [t for t in task_ids if FROM_EMAIL not in owner_map.get(t, set())]
both = [t for t in task_ids if TO_EMAIL in owner_map.get(t, set())]
drafts = AnnotationDraft.objects.filter(task_id__in=task_ids, user=src).count()
done = set(
    project.tasks.filter(
        id__in=task_ids, annotations__completed_by=src, annotations__was_cancelled=False
    ).values_list('id', flat=True)
)

print('任务数        ', len(task_ids))
print('当前不属于 %s' % FROM_EMAIL, len(lost), lost[:5])
print('已同时属于 %s' % TO_EMAIL, len(both), both[:5])
print('%s 的草稿' % FROM_EMAIL, drafts, '（转派后他将看不到这些草稿，草稿本身不删）')
print('%s 已提交其中' % FROM_EMAIL, len(done), '张 —— 这些不该出现在列表里' if done else '')

if not APPLY:
    print('\n[DRY-RUN] 未写库。确认无误后把 APPLY 改成 True 再跑。')
else:
    stats = apply_task_assignments(project, task_ids, [dst.id], actor)
    print('\n已执行：', stats)
    print('复核：')
    after = {}
    for row in TaskAssignment.objects.filter(task_id__in=task_ids).values('task_id', 'user__email'):
        after.setdefault(row['task_id'], set()).add(row['user__email'])
    bad = [t for t in task_ids if after.get(t) != {TO_EMAIL}]
    print('  归属不属于 %s 的任务数：%d' % (TO_EMAIL, len(bad)))
    print('  %s 剩余分配：%d' % (TO_EMAIL, TaskAssignment.objects.filter(user=dst, task__project=project).count()))
    print('  %s 剩余分配：%d' % (FROM_EMAIL, TaskAssignment.objects.filter(user=src, task__project=project).count()))
