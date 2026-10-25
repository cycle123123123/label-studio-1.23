"""把齐添乐（1@163.com）未完成的 162 张单人任务转派给孙无双（3@163.com）。

只动单人段，交叉集不动。MODE 控制方向，APPLY 控制是否写库。

服务器上执行（cwd/PYTHONPATH = /label-studio/label_studio，脚本在宿主机仓库里）：

  # 1) 先核对，不写库
  docker compose exec -T app python manage.py shell < scripts/transfer_qi_solo_to_sun.py
  # 2) 核对无误后把 APPLY 改成 True，重跑同一条命令
  # 3) 需要撤销时把 MODE 改成 'rollback'，APPLY=True 再跑

语义：apply_task_assignments 对这批任务做「覆盖式」赋值 —— assignees 里没有的人会被移除，
所以一次调用即完成 移除齐 / 加入孙，中间不留无人可标的状态。
"""

import os

from django.contrib.auth import get_user_model

from projects.models import Project
from tasks.assignment import apply_task_assignments
from tasks.models import AnnotationDraft, TaskAssignment

# ---------------- CONFIG ----------------
PROJECT_ID = 1
QI = '1@163.com'        # 齐添乐 user id 2
SUN = '3@163.com'       # 孙无双 user id 4
ACTOR = '13243186667'   # 执行人（管理员）
MODE = os.environ.get('MODE', 'transfer')   # transfer | rollback
APPLY = os.environ.get('APPLY', '0') in ('1', 'true', 'yes', 'y')

TASK_IDS = [
    5048, 5054, 5056, 5057, 5102, 5103, 5109, 5117, 5118, 5119, 5121, 5122,
    5123, 5124, 5126, 5127, 5128, 5129, 5131, 5132, 5133, 5134, 5136, 5137,
    5138, 5139, 5141, 5142, 5143, 5144, 5146, 5147, 5148, 5149, 5151, 5152,
    5153, 5154, 5156, 5157, 5158, 5159, 5161, 5162, 5163, 5164, 5166, 5167,
    5168, 5169, 5171, 5172, 5173, 5174, 5176, 5177, 5178, 5179, 5195, 5196,
    5197, 5198, 5200, 5201, 5202, 5203, 5205, 5206, 5207, 5208, 5210, 5211,
    5212, 5213, 5215, 5216, 5217, 5218, 5220, 5221, 5222, 5223, 5225, 5226,
    5227, 5228, 5230, 5231, 5232, 5233, 5235, 5236, 5237, 5238, 5240, 5241,
    5242, 5243, 5245, 5246, 5247, 5248, 5250, 5251, 5252, 5253, 5255, 5256,
    5257, 5258, 5260, 5261, 5262, 5263, 5265, 5266, 5267, 5268, 5270, 5271,
    5272, 5273, 5275, 5276, 5277, 5278, 5280, 5281, 5282, 5283, 5285, 5286,
    5287, 5288, 5290, 5291, 5292, 5293, 5295, 5296, 5297, 5298, 5300, 5301,
    5302, 5303, 5305, 5306, 5307, 5308, 5310, 5311, 5312, 5313, 5315, 5316,
    5317, 5318, 5320, 5321, 5322, 5323,
]

# ----------------------------------------

User = get_user_model()
project = Project.objects.get(pk=PROJECT_ID)
qi = User.objects.get(email=QI)
sun = User.objects.get(email=SUN)
actor = User.objects.get(email=ACTOR)

owners = {}
for row in TaskAssignment.objects.filter(task_id__in=TASK_IDS).values('task_id', 'user__email'):
    owners.setdefault(row['task_id'], set()).add(row['user__email'])

not_qi = [t for t in TASK_IDS if QI not in owners.get(t, set())]
has_sun = [t for t in TASK_IDS if SUN in owners.get(t, set())]
drafts = AnnotationDraft.objects.filter(task_id__in=TASK_IDS, user=qi).count()
submitted = set(
    project.tasks.filter(
        id__in=TASK_IDS, annotations__completed_by=qi, annotations__was_cancelled=False
    ).values_list('id', flat=True)
)

print('=' * 52)
print('任务数              ', len(TASK_IDS))
print('已不属于 %s      ' % QI, len(not_qi), not_qi[:5])
print('已属于 %s        ' % SUN, len(has_sun), has_sun[:5])
print('%s 的草稿        ' % QI, drafts, '(转派后看不到，草稿不删)' if drafts else '')
print('%s 已提交其中    ' % QI, len(submitted), '(不该 >0)' if submitted else '')

target = sun if MODE == 'transfer' else qi
if not APPLY:
    print('-' * 52)
    print('[DRY-RUN] 未写库。确认无误后把 APPLY 改成 True 重跑。')
else:
    stats = apply_task_assignments(project, TASK_IDS, [target.id], actor)
    print('-' * 52)
    print('已执行 %s -> %s : %s' % (MODE, target.email, stats))
    after = {}
    for row in TaskAssignment.objects.filter(task_id__in=TASK_IDS).values('task_id', 'user__email'):
        after.setdefault(row['task_id'], set()).add(row['user__email'])
    bad = [t for t in TASK_IDS if after.get(t) != {target.email}]
    print('复核：归属异常 %d 张 %s' % (len(bad), bad[:5]))
    print('  孙无双 剩余分配：%d' % TaskAssignment.objects.filter(user=sun, task__project=project).count())
    print('  齐添乐 剩余分配：%d' % TaskAssignment.objects.filter(user=qi, task__project=project).count())
print('=' * 52)
