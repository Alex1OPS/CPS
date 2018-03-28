import os

import docplex.cp.utils_visu as visu
from docplex.cp.model import CpoModel, CpoStepFunction, INTERVAL_MIN, INTERVAL_MAX
import functools
import math

sign = functools.partial(math.copysign, 1)

DAYS_IN_SPRINT = 14
HOURS_IN_DAY = 24

def to_matrix(s, dev_count):
    m = []
    for i in range(dev_count):
        da = []
        for j in range(DAYS_IN_SPRINT):
            hr = []
            for k in range(HOURS_IN_DAY):
                hr.append(s[j * HOURS_IN_DAY + k])
            da.append(hr)
        m.append(da)
    return m


def make_resource_row(rnd, dev_count, duration):
    r = [0] * dev_count
    r[rnd] = duration
    return r

# -----------------------------------------------------------------------------
# Подготовка данных
# -----------------------------------------------------------------------------

# Описание файла
# 1 строка - список количества задач для разработчиков
# строки 2:NB_RESOURCES+1 - матрицы активности разработчиков (матрица i разработчика развёрнута в строку)
# NUM_DEV_TASKS строк с задачами: оценка по времени, приоритет, крайний срок


filename = os.path.dirname(os.path.abspath(__file__)) + "/data/rnd.data"
with open(filename, "r") as file:
    NUM_DEV_TASKS = [int(i) for i in file.readline().split()]
    NB_TASKS = sum(NUM_DEV_TASKS)
    NB_RESOURCES = len(NUM_DEV_TASKS)
    MM_DEV_ACTIVE_HOURS = to_matrix([int(i) for j in range(NB_RESOURCES) for i in file.readline().split()], NB_RESOURCES)
    CAPACITIES = [sum(map(sum, MM_DEV_ACTIVE_HOURS[i])) for i in range(NB_RESOURCES)]

    TASKS = []
    for i in range(NB_RESOURCES):
        for _ in range(NUM_DEV_TASKS[i]):
            v = file.readline().split()
            TASKS.append({"duration": int(v[0]), "rank": int(v[1]), "deadline": int(v[2]), "rnd": i})

    LINKED_TASKS_COUNT = int(file.readline())
    LINKED_TASKS = []
    for i in range(LINKED_TASKS_COUNT):
        s = file.readline().split()
        LINKED_TASKS.append({"task_num": int(s[0]), "linked_rnd": int(s[1])})

for i, k in enumerate(NUM_DEV_TASKS):
    print("Developer {0} has {1} tasks for {2} hours".format(i, k, CAPACITIES[i]))
print("Total tasks in sprint: {} for {} developers".format(NB_TASKS, NB_RESOURCES))

# Продолжительность задач
DURATIONS = [TASKS[t]["duration"] for t in range(NB_TASKS)]

# Требования задач к ресурсам - тут всё просто - 1 разраб = 1 задача
DEMANDS = [make_resource_row(TASKS[t]["rnd"], NB_RESOURCES, DURATIONS[t]) for t in range(NB_TASKS)]

# построим список функций "присутсвия на работе"
RND_CALENDAR = []
for i in range(NB_RESOURCES):
    print("Calendar function for rnd {}".format(i))
    cnst_pr = [0, 0]
    last_val = sign(MM_DEV_ACTIVE_HOURS[i][0][0])
    fs = CpoStepFunction()
    fs.set_value(0, DAYS_IN_SPRINT * HOURS_IN_DAY, 100)
    for fdays, farrhr in enumerate(MM_DEV_ACTIVE_HOURS[i]):
        for fhours, fval in enumerate(farrhr):
            if fval == last_val == 0:
                cnst_pr[1] = fdays * HOURS_IN_DAY + fhours
            elif fval == 1 and last_val == 0:
                fs.set_value(cnst_pr[0], cnst_pr[1], 0)
                # print("find interval from {} to {}".format(cnst_pr[0], cnst_pr[1]))
                cnst_pr[0] = cnst_pr[1] = fdays * HOURS_IN_DAY + fhours
            elif fval == 0 and last_val == 1:
                cnst_pr[0] = cnst_pr[1] = fdays * HOURS_IN_DAY + fhours
            last_val = fval
    RND_CALENDAR.append(fs)

# -----------------------------------------------------------------------------
# Описание модели
# -----------------------------------------------------------------------------

mdl = CpoModel()
# задача = interval variables
tasks = [mdl.interval_var(name="T{}".format(i + 1), size=DURATIONS[i]) for i in range(NB_TASKS)]

# ОГРАНИЧЕНИЯ #
# Учтём приоритеты
for i in range(NB_RESOURCES):
    successors_tasks = []
    high_priority = []
    for k, j in enumerate(TASKS):
        if j["rnd"] == i and j["rank"] == 0:
            successors_tasks.append(k)
        if j["rnd"] == i and j["rank"] == 1:
            high_priority.append(k)

    for s in high_priority:
        for m in successors_tasks:
            mdl.add(mdl.end_before_start(tasks[m], tasks[s]))

# Учтём ресурсы (разработчиков)
for r in range(NB_RESOURCES):
    resources = [mdl.pulse(tasks[t], DEMANDS[t][r]) for t in range(NB_TASKS) if DEMANDS[t][r] > 0]
    mdl.add(mdl.sum(resources) <= CAPACITIES[r])

# одновременно только одна задача
for i in range(NB_RESOURCES):
    lops = []
    for k, j in enumerate(TASKS):
        if j["rnd"] == i:
            lops.append(tasks[k])
    mdl.add(mdl.no_overlap(lops))

# Учтём матрицу активности
for i in LINKED_TASKS:
    for k, j in enumerate(TASKS):
        if k == i["task_num"]:
            mdl.add(mdl.forbid_start(tasks[k], RND_CALENDAR[i["linked_rnd"]]))
            mdl.add(mdl.forbid_end(tasks[k], RND_CALENDAR[i["linked_rnd"]]))

for k, j in enumerate(TASKS):
    mdl.add(mdl.forbid_start(tasks[k], RND_CALENDAR[j["rnd"]]))
    mdl.add(mdl.forbid_end(tasks[k], RND_CALENDAR[j["rnd"]]))

# Минимизируем время завершения последней задачи
mdl.add(mdl.minimize(mdl.max([mdl.end_of(t) for t in tasks])))

# -----------------------------------------------------------------------------
# Решение solver'ом и вывод
# -----------------------------------------------------------------------------

print("Solving model....")
msol = mdl.solve(FailLimit=100000, TimeLimit=10)
print("Solution: ")
msol.print_solution()
#
if msol and visu.is_visu_enabled():
    load = [CpoStepFunction() for j in range(NB_RESOURCES)]
    for i in range(NB_TASKS):
        itv = msol.get_var_solution(tasks[i])
        for j in range(NB_RESOURCES):
            if 0 < DEMANDS[i][j]:
                load[j].add_value(itv.get_start(), itv.get_end(), DEMANDS[i][j])

    visu.timeline("Solution for R'n'D problem")
    visu.panel("Tasks")
    for i in range(NB_TASKS):
        visu.interval(msol.get_var_solution(tasks[i]), i, tasks[i].get_name())
    for j in range(NB_RESOURCES):
        visu.panel("R " + str(j + 1))
        visu.function(segments=[(INTERVAL_MIN, INTERVAL_MAX, CAPACITIES[j])], style='area', color='lightgrey')
        visu.function(segments=load[j], style='area', color=j)
    visu.show()
