import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np


# Configuration 1
CONFIG = {
    "title": "Планы по зарплатам в 2025 году",
    "xlabel": "% компаний",
    "xlim": [-100, 100],
    "img_name": "img_1.png",
    "colormaps": {
        "green": ["#2D5F2E", "#8CB369"],
        "red": ["#C14953", "#6D1A1A"]
    },
    "bar_width": 0.65,
    "left_ticks": 1,
    "font": "Arial",
    "grid_color": "#EAEAEA",
    "text_colors": {
        "green": "#FFFFFF",
        "red": "#FFFFFF"
    },
    "ticks": [
        "Увеличить",
        "Оставить на прежнем уровне",
        "Сократить",
        "Затруднились ответить",
    ],
    "data": {
        "Автомобильный бизнес": [43, 21, 0, 36],
        "Информационные технологии (ИТ, IT)": [62, 20, 0, 18],
        "Логистика": [84, 8, 0, 8],
        "Медицина и фармацевтика": [65, 22, 0, 13],
        "Медицинское и лабораторное оборудование": [70, 10, 0, 20],
        "Металлургия": [73, 18, 0, 9],
        "Строительство": [49, 36, 0, 15],
        "Товары народного потребления (FMCG), в т.ч. табак и алкоголь": [76, 11, 3, 10],
        "Финансовые институты": [50, 38, 0, 12],
        "Химическое сырье": [60, 20, 0, 20],
    }
}

# Configuration 2
# CONFIG = {
#     "xlabel": "% компаний",
#     "img_name": "img_2.png",
#     "colormaps": {
#         "green": ["#2D5F2E", "#8CB369"],
#         "red": ["#C14953", "#6D1A1A"]
#     },
#     "bar_width": 0.65,
#     "left_ticks": 3,
#     "font": "Arial",
#     "grid_color": "#EAEAEA",
#     "text_colors": {
#         "green": "#FFFFFF",
#         "red": "#FFFFFF"
#     },
#     "title": "Как прошёл 2024 год в вашей компании?",
#     "ticks": [
#         "Лучше, чем 2023",
#         "Лучше, чем 2023, но хуже 2022",
#         "Лучше, чем 2022, но хуже 2020",
#         "Так же, как и прошлый",
#         "Хуже, чем 2023"
#     ],
#     "data": {
#         "В целом": [31, 5, 2, 19, 43],
#         "Тяжелая промышленность": [40, 4, 0, 18, 38],
#         "ИТ": [34, 6, 4, 20, 36],
#         "Легкая промышленность": [33, 6, 0, 19, 42],
#         "Финансовые технологии": [31, 3, 4, 14, 48],
#         "Розничная торговля": [31, 4, 3, 16, 46],
#         "Строительство, недвижимость": [30, 5, 0, 22, 43],
#         "Услуги для бизнеса и населения": [30, 5, 2, 22, 41],
#         "Добыча и переработка ископаемых": [28, 5, 1, 20, 46],
#         "Гостиницы, рестораны": [27, 2, 2, 15, 54],
#         "Логистика": [23, 7, 2, 18, 50]
#     },
#     "xlim": [-65, 75]
# }

# Sort the data
CONFIG['data'] = dict(
    sorted(CONFIG['data'].items(), key=lambda x: sum(x[1][: CONFIG['left_ticks']]), reverse=False))


def create_colormaps():
    """Create LinearSegmentedColormap objects from the CONFIG colormaps."""
    cmaps = {}
    for name, colors in CONFIG["colormaps"].items():
        cmaps[name] = mcolors.LinearSegmentedColormap.from_list(name, colors)
    return cmaps


def add_labels(ax, bars, values, color_type):
    """Add value labels to the bars with appropriate text color."""
    text_color = CONFIG["text_colors"][color_type]
    for bar, value in zip(bars, values):
        if value == 0:
            continue
        width = bar.get_width()
        x = bar.get_x() + width / 2
        y = bar.get_y() + bar.get_height() / 2
        ax.text(x, y, f"{int(value)}",
                ha='center', va='center',
                color=text_color, fontsize=14)


def add_style(ax):
    """Apply professional styling elements."""
    plt.rcParams['font.family'] = CONFIG["font"]
    ax.xaxis.grid(True, color=CONFIG["grid_color"], linestyle='--')
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.axvline(0, color='#404040', linewidth=0.8, alpha=0.8)


def plot_segments(ax, data, cmaps):
    """Plot the horizontal bar segments with correct colors."""
    categories = list(data.keys())
    params = [
        {'direction': 'left', 'cmap': cmaps['green'], 'color': 'green',
         'indices': range(CONFIG["left_ticks"]), 'edgecolor': '#404040'},
        {'direction': 'right', 'cmap': cmaps['red'], 'color': 'red',
         'indices': range(CONFIG["left_ticks"], len(CONFIG["ticks"])), 'edgecolor': '#404040'}
    ]

    for param in params:
        base = np.zeros(len(categories))
        for idx, data_idx in enumerate(param['indices']):
            values = np.array([v[data_idx] for v in data.values()])
            width = -values if param['direction'] == 'left' else values
            norm_idx = idx / (len(param['indices']) - 0.8)
            color = param['cmap'](norm_idx)
            bars = ax.barh(
                np.arange(len(categories)), width,
                left=base, height=CONFIG["bar_width"],
                color=color, edgecolor=param['edgecolor'],
                linewidth=0.5, alpha=0.95
            )
            add_labels(ax, bars, values, param['color'])
            base += width


def create_plot(data):
    """Create the final plot with correct legend colors."""
    plt.rcParams['font.size'] = 12
    fig, ax = plt.subplots(figsize=(15, 8))

    ax.set_title(CONFIG["title"], fontsize=18, pad=20, color='#2D2D2D', weight='semibold', y=1.2, x=0.27)
    ax.set_yticks(np.arange(len(data)))
    ax.set_yticklabels(data.keys(), color='#404040', fontsize=11)
    ax.set_xlim(*CONFIG['xlim'])
    ax.set_xticks([])

    cmaps = create_colormaps()
    plot_segments(ax, data, cmaps)
    add_style(ax)

    # Generate correct legend colors
    tick_colors = []
    for i in range(len(CONFIG["ticks"])):
        if i < CONFIG["left_ticks"]:
            cmap = cmaps['green']
            pos = i / (CONFIG["left_ticks"] - 0.8)
        else:
            cmap = cmaps['red']
            idx = i - CONFIG["left_ticks"]
            pos = idx / ((len(CONFIG["ticks"]) - CONFIG["left_ticks"]) - 0.8)
        tick_colors.append(cmap(pos))

    # Create legend handles
    legend_handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in tick_colors]

    # Add legend
    legend = ax.legend(
        handles=legend_handles,
        labels=CONFIG["ticks"],
        ncol=2, frameon=False,
        loc=(0.13, 1.05), fontsize=12
    )
    for text in legend.get_texts():
        text.set_color('#606060')

    plt.subplots_adjust(top=0.88, bottom=0.15)
    plt.xlabel(CONFIG['xlabel'])
    plt.tight_layout()
    plt.savefig(CONFIG['img_name'], format='png', dpi=120)


if __name__ == "__main__":
    create_plot(CONFIG['data'])