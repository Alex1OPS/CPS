import docplex.cp.utils_visu as visu
from docplex.cp.model import CpoModel

# Заведено 3 навыка - не будем городить классы и namedtuple'ы, т.к. будет проще записывать ограничения
# (и сложнее разобраться в коде :D )
# список несёт чисто информационную функцию
SKILLS = ["Монтаж кабеля", "Монтаж антенны", "Настройка ПО"]
# Список монтажников (имя, уровни навыков)
INSTALLERS = [
    ("Иван", 7, 6, 4),
    ("Вася", 8, 2, 7),
    ("Петя", 3, 9, 6)
]
# Перечень заказов (продолжительность, наименование, указание требуемого уровня к списку навыков (0 - не требуется))
WAIT_ORDERS = [(2, "Выезд на Соломенную", 5, 0, 2),
               (1, "Выезд в ТРЦ", 8, 1, 1),
               (2, "Точка 1", 0, 8, 5),
               (4, "Установка комплекта", 3, 4, 2),
               (3, "В склад", 6, 5, 2),
               (6, "Магазин на стройке", 3, 3, 3)
               ]
# Рассчитанная матрица путей между точками всех заказов
PATH_POINTS_TIMES = [
    0, 1, 1, 1, 1, 1,
    1, 0, 1, 1, 1, 1,
    1, 1, 0, 1, 1, 1,
    1, 1, 1, 0, 1, 1,
    1, 1, 1, 1, 0, 1,
    1, 1, 1, 1, 1, 0
]

MAX_SCHEDULE = 40
ORDERS_COUNT = len(WAIT_ORDERS)
WORKERS_COUNT = len(INSTALLERS)
TASK_TEMPLATE_NAME = "T{num} - {name}"


def print_tasks(tt):
    for i, v in enumerate(tt):
        print("Tasks for worker {}".format(INSTALLERS[i][0]))
        for p in v:
            print("... task = {}".format(p.get_name()))


# Построим модель
mdl = CpoModel()

tasks = []

# заведём задачи по монтажникам
for i in range(WORKERS_COUNT):
    worker_tasks = []
    for j in range(ORDERS_COUNT):
        if all([(a >= b) for a, b in zip(INSTALLERS[i][1:], WAIT_ORDERS[j][2:])]):
            worker_tasks.append(
                mdl.interval_var(size=WAIT_ORDERS[j][0],
                                 name=TASK_TEMPLATE_NAME.format(num=str(j), name=WAIT_ORDERS[j][1]),
                                 start=(0, MAX_SCHEDULE),
                                 end=(0, MAX_SCHEDULE),
                                 optional=True)
            )
    tasks.append(worker_tasks)

# посмотрим, что создали
# print_tasks(tasks)


# одна задача - один монтажник
for i in range(WORKERS_COUNT):
    for j in range(len(tasks[i])):
        a_t = tasks[i][j].get_name()

        alternative_tasks = []
        for i_alt in range(WORKERS_COUNT):
            for j_alt in range(len(tasks[i_alt])):
                if i_alt == i: continue
                if a_t == tasks[i_alt][j_alt].get_name():
                    alternative_tasks.append(tasks[i_alt][j_alt])

        if len(alternative_tasks) != 0:
            mdl.add(mdl.alternative(tasks[i][j], alternative_tasks))

        # alternative_tasks = [tasks[p][k] for p in range(WORKERS_COUNT) for k in range(len(tasks[p])) if
        #                      tasks[p][k].get_name() == a_t and p != i]
        # alternative_worker = [(INSTALLERS[p][0], p) for p in range(WORKERS_COUNT) for k in range(len(tasks[p])) if
        #                       tasks[p][k].get_name() == a_t and p != i]
        # if len(alternative_tasks) != 0:
        #     mdl.add(mdl.alternative(tasks[i][j], alternative_tasks))

        # посмотрим, какие альтернативные задачи у нас есть
        # print("Alters for worker {} and task {}".format(INSTALLERS[i][0], tasks[i][j].get_name()))
        # for sp, v in enumerate(alternative_tasks):
        #     print("... {} of {}".format(v.get_name(), alternative_worker[sp][0]))


# в один момент времени - одна задача
for i in range(WORKERS_COUNT):
    mdl.add(mdl.no_overlap(tasks[i]))

# все задачи должны быть выполнены
for i in range(ORDERS_COUNT):
    a_t = TASK_TEMPLATE_NAME.format(num=str(i), name=WAIT_ORDERS[i][1])
    mdl.add(mdl.sum([mdl.presence_of(t) for k in tasks for t in k if t.get_name() == a_t]) > 0)


# OF
mdl.add(mdl.minimize(mdl.max([mdl.end_of(t) * mdl.presence_of(t) for i, tp in enumerate(tasks) for j, t in enumerate(tp) ])))

# вывод решения
print("Solving model....")
msol = mdl.solve(FailLimit=10000000, TimeLimit=100)
print("Solution: ")
# msol.print_solution()

for w in range(WORKERS_COUNT):
        #visu.sequence(name=WORKER_NAMES[w])
        print("Tasks of worker {}".format(INSTALLERS[w][0]))
        for t in tasks[w]:
            wt = msol.get_var_solution(t)
            if wt.is_present():
                print("... {}".format(wt.get_name()))
