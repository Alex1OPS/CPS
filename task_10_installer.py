import docplex.cp.utils_visu as visu
from docplex.cp.model import CpoModel
from transliterate import translit

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
               (6, "Магазин на стройке", 3, 3, 3),
               (1, "Разовый 1", 3, 6, 4),
               (3, "Разовый 2", 3, 6, 4),
               (3, "Разовый 3", 6, 1, 3),
               (2, "Разовый 4", 2, 1, 1)
               ]
# Рассчитанная матрица путей между точками всех заказов
# PATH_POINTS_TIMES = [
#     [0, 0, 1, 0],
#     [0, 0, 1, 0],
#     [1, 1, 1, 1],
#     [1, 1, 1, 1]
# ]
PATH_POINTS_TIMES = [
    [1, 1, 1, 1, 1, 1, 1, 1],
    [0, 1, 1, 1, 2, 1, 1, 1],
    [1, 1, 1, 2, 1, 1, 1, 1],
    [2, 1, 1, 2, 0, 1, 1, 1],
    [2, 1, 1, 2, 1, 1, 1, 1],
    [2, 1, 2, 1, 1, 1, 1, 1],
    [2, 1, 2, 1, 1, 1, 1, 1],
    [2, 1, 2, 1, 1, 1, 1, 1]
]

MAX_SCHEDULE = 12
ORDERS_COUNT = len(WAIT_ORDERS)
WORKERS_COUNT = len(INSTALLERS)
TASK_TEMPLATE_NAME = "T{num} - {name}"


def find_distance(ivp, j):
    i_name = ivp.get_name()
    j_name = j.get_name()
    i_ind = [x[1] for x in WAIT_ORDERS].index(i_name)
    j_ind = [x[1] for x in WAIT_ORDERS].index(j_name)
    return PATH_POINTS_TIMES[i_ind][j_ind]


def print_tasks(tt):
    for ivp, v in enumerate(tt):
        print("Tasks for worker {}".format(INSTALLERS[ivp][0]))
        for p in v:
            print("... task = {}".format(p.get_name()))


def trans_ru(text):
    return translit(text, 'ru', reversed=True)


def compact_name(text):
    return text.split(" - ")[0]


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

# Реально выполняемые задачи
tasks_act = [mdl.interval_var(name="T{}_{}".format(str(i), WAIT_ORDERS[i][1]),
                              size=WAIT_ORDERS[i][0],
                              start=(0, MAX_SCHEDULE),
                              end=(0, MAX_SCHEDULE)) for i in range(ORDERS_COUNT)]

# одна задача - один монтажник
for i in range(ORDERS_COUNT):
    a_t = WAIT_ORDERS[i][1]
    kk = [tasks[p][k] for p in range(WORKERS_COUNT) for k in range(len(tasks[p])) if (tasks[p][k].get_name() == a_t)]
    if len(kk) != 0:
        mdl.add(mdl.alternative(tasks_act[i], kk, 1))

# в один момент времени - одна задача
for i in range(WORKERS_COUNT):
    mdl.add(mdl.no_overlap(tasks[i]))

# все задачи должны быть выполнены
for i in range(ORDERS_COUNT):
    a_t = TASK_TEMPLATE_NAME.format(num=str(i), name=WAIT_ORDERS[i][1])
    mdl.add(mdl.sum([mdl.presence_of(t) for k in tasks for t in k if t.get_name() == a_t]) > 0)

# OF
mdl.add(
    mdl.minimize(mdl.max([mdl.end_of(t) * mdl.presence_of(t) for i, tp in enumerate(tasks) for j, t in enumerate(tp)]))
)

# добавим учёт времени на переходы
workers_sequence = []
for i in range(WORKERS_COUNT):
    s = mdl.sequence_var(tasks[i], name="{}".format(INSTALLERS[i][0]), types=[x for x in range(len(tasks[i]))])
    workers_sequence.append(s)
    mdl.add(mdl.no_overlap(s, mdl.transition_matrix(szvals=PATH_POINTS_TIMES, name="DD")))

# вывод решения
print("Solving model....")
msol = mdl.solve(FailLimit=10000000, TimeLimit=60 * 3, LogVerbosity="Terse")
print("Solution: ")
# msol.print_solution()

if msol and visu.is_visu_enabled():
    for w in range(WORKERS_COUNT):
        print("Task for installer {}".format(INSTALLERS[w][0]))
        visu.sequence(name=trans_ru(INSTALLERS[w][0]))
        for i, t in enumerate(tasks[w]):
            wt = msol.get_var_solution(t)
            if wt.is_present():
                print("--- {}".format(wt.get_name()))
                visu.interval(wt, i, compact_name(trans_ru(wt.get_name())))
    visu.show()
