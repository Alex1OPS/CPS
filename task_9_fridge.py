import random
from collections import namedtuple

import docplex.cp.utils_visu as visu
from docplex.cp.model import CpoModel, CpoStepFunction

# Размер полки
SIZE_SHELF = {"x": 80, "y": 50}
# Количество полок
SHELF_COUNT = 3
# Температурные режимы
T = [[0, 8], [7, 12], [0, 3]]
E = [3, 2, 10]
# Матрица энергий по продуктам/полкам
SHELVES_PRODUCT_MATRIX = []

ShelfType = namedtuple("ShelfType", ['x_start', 'x_stop', 'y_start', 'y_stop', 't_min', 't_max', 'e_energy'])
ProductCat = namedtuple("ProductCat", ['name', 'code'])

# Опишем категории продуктов
FRUITS = ProductCat(name="Fruits", code=1)
VEGETABLES = ProductCat(name="Vegetables", code=3)
MEAT = ProductCat(name="Meat", code=3)
MILK = ProductCat(name="Milk", code=4)
FISH = ProductCat(name="Fish", code=5)
BAKE = ProductCat(name="Bake", code=6)

# Пары несовместимых групп продуктов
INCOMPATIBLE_GROUPS = (
    (FRUITS, FISH),
    (VEGETABLES, FISH),
    (MEAT, BAKE),
    (MILK, FISH)
)


# функция возвращает допустимый для продукта интервал внутри полок
# с подходящей температурой
def get_allowable_area(shls, ax_attr, temperature):
    f_ = CpoStepFunction()
    if ax_attr == 'x':
        f_.set_value(0, SIZE_SHELF["x"] * SHELF_COUNT, 100)
        for ih in range(len(shls)):
            f_.set_value(shls[ih].x_start, shls[ih].x_start + 1, 0)
            f_.set_value(shls[ih].x_stop - 1, shls[ih].x_stop, 0)
            if not shls[ih].t_min <= temperature <= shls[ih].t_max:
                f_.set_value(shls[ih].x_start, shls[ih].x_stop, 0)
    elif ax_attr == 'y':
        f_.set_value(0, SIZE_SHELF["y"] * SHELF_COUNT, 100)
        for ih in range(len(shls)):
            f_.set_value(shls[ih].y_start, shls[ih].y_start + 1, 0)
            f_.set_value(shls[ih].y_stop - 1, shls[ih].y_stop, 0)
            if not shls[ih].t_min <= temperature <= shls[ih].t_max:
                f_.set_value(shls[ih].y_start, shls[ih].y_stop, 0)
    return f_


# получение затрат в Дж на охлаждение 1 кг продукта
def get_prepared_energy(pos, product_ind):
    return SHELVES_PRODUCT_MATRIX[pos][product_ind]


# -----------------------------------------------------------------------------
# Подготовка данных
# -----------------------------------------------------------------------------
# Создадим набор полок с характеристиками
SHELVES = []
for i in range(SHELF_COUNT):
    o = ShelfType(x_start=i * SIZE_SHELF["x"], x_stop=(i + 1) * SIZE_SHELF["x"], y_start=0, y_stop=SIZE_SHELF["y"],
                  t_min=T[i][0], t_max=T[i][1], e_energy=E[i])
    SHELVES.append(o)

# Размеры продуктов
WEIGHT_SIZE_A = [25, 17, 16, 15, 11,
                 9, 8, 7, 6, 4,
                 2, 20, 20, 10, 60]
WEIGHT_SIZE_B = [10, 15, 2, 4, 8,
                 9, 3, 5, 2, 3,
                 1, 20, 20, 30, 40]
PRODUCT_T = [0, 7, 11, 2, 3,
             8, 5, 12, 2, 3,
             1, 1, 1, 1, 1]
PRODUCT_WEIGHT = [2, 7, 11, 2, 3,
                  8, 5, 12, 2, 3,
                  1, 1, 1, 1, 1]
PRODUCT_NAMES = ["m" + str(i) for i in range(len(WEIGHT_SIZE_A))]
PRODUCT_CATS = [FRUITS, FRUITS, FRUITS, FRUITS, FRUITS,
                FRUITS, FRUITS, FRUITS, FRUITS, FRUITS,
                FRUITS, FRUITS, FRUITS, FISH, FRUITS]
NB_WEIGHTS = len(WEIGHT_SIZE_A)

if not len(WEIGHT_SIZE_A) == len(WEIGHT_SIZE_B) == len(PRODUCT_T):
    raise RuntimeError("Не совпадают размерности матриц продуктов!")

for i in range(len(PRODUCT_WEIGHT)):
    p = []
    for j in range(SIZE_SHELF["x"] * SHELF_COUNT):
        p.append(E[int(j / SIZE_SHELF["x"])] * PRODUCT_WEIGHT[i])
    SHELVES_PRODUCT_MATRIX.append(p)

# -----------------------------------------------------------------------------
# Описание модели
# -----------------------------------------------------------------------------
mdl = CpoModel()

# Создадим массивы продуктов по сторонам
vx = [mdl.interval_var(size=WEIGHT_SIZE_A[i], name="X" + str(i), end=(0, SIZE_SHELF["x"] * SHELF_COUNT)) for i in
      range(NB_WEIGHTS)]
vy = [mdl.interval_var(size=WEIGHT_SIZE_B[i], name="Y" + str(i), end=(0, SIZE_SHELF["y"] * 1)) for i in
      range(NB_WEIGHTS)]

# Запретим пересекать границы полок и учтём температуры
for i in range(NB_WEIGHTS):
    mdl.add(mdl.forbid_extent(vx[i], get_allowable_area(SHELVES, 'x', PRODUCT_T[i])))


# Запретим пересечение продуктов
for i in range(NB_WEIGHTS):
    for j in range(i):
        mdl.add((mdl.end_of(vx[i]) <= mdl.start_of(vx[j])) | (mdl.end_of(vx[j]) <= mdl.start_of(vx[i]))
                | (mdl.end_of(vy[i]) <= mdl.start_of(vy[j])) | (mdl.end_of(vy[j]) <= mdl.start_of(vy[i])))

# Соберём списки продуктов, которые не могут быть рядом
for i in range(NB_WEIGHTS):
    for j in range(i):
        if ((PRODUCT_CATS[i], PRODUCT_CATS[j]) in INCOMPATIBLE_GROUPS) or ((PRODUCT_CATS[j], PRODUCT_CATS[i]) in INCOMPATIBLE_GROUPS):
            print("Find incompatible group ({}, {})".format(PRODUCT_NAMES[i], PRODUCT_NAMES[j]))
            mdl.add(mdl.logical_not(
                (mdl.start_of(vx[i]) == mdl.end_of(vx[j]))
                | (mdl.start_of(vx[j]) == mdl.end_of(vx[i]))
                | (mdl.start_of(vy[i]) == mdl.end_of(vy[j]))
                | (mdl.start_of(vy[j]) == mdl.end_of(vy[i]))
            ))


# OF - минимум энергии, необходимой для поддержания температурных режимов продуктов на полках
mdl.add(mdl.minimize(
    mdl.sum(
        mdl.element(SHELVES_PRODUCT_MATRIX[t], mdl.start_of(vx[t])) for t in range(len(vx))
    )
))

mdl.set_search_phases([mdl.search_phase(vx), mdl.search_phase(vy)])

# -----------------------------------------------------------------------------
# Решение solver'ом и вывод
# -----------------------------------------------------------------------------
print("Solving model....")
msol = mdl.solve(FailLimit=100000000, TimeLimit=60 * 10, LogVerbosity="Terse", # use "Quiet" or "Terse"
                 RandomSeed=random.randint(1, 1000), OptimalityTolerance=1.0, RelativeOptimalityTolerance=1.0)
print("Solution: ")
msol.print_solution()

if msol and visu.is_visu_enabled():
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    from matplotlib.patches import Polygon, Rectangle

    print("Plotting ....")
    c_map = plt.get_cmap('gist_rainbow')
    fig, ax = plt.subplots()
    width = SIZE_SHELF["x"]
    height = SIZE_SHELF["y"]
    for i in range(SHELF_COUNT):
        ax.add_patch(Rectangle((i * width, 0), width, height, facecolor=c_map(1. * i / SHELF_COUNT), alpha=0.08))
    for i in range(NB_WEIGHTS):
        sx, sy = msol.get_var_solution(vx[i]), msol.get_var_solution(vy[i])
        (sx1, sx2, sy1, sy2) = (sx.get_start(), sx.get_end(), sy.get_start(), sy.get_end())
        poly = Polygon([(sx1, sy1), (sx1, sy2), (sx2, sy2), (sx2, sy1)], fc=cm.Set2(float(i) / NB_WEIGHTS))
        ax.add_patch(poly)
        ax.text(float(sx1 + sx2) / 2, float(sy1 + sy2) / 2, PRODUCT_NAMES[i], ha='center', va='center')
    plt.margins(0)
    plt.show()
