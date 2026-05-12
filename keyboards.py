"""
Клавиатуры WatchList Bot v2 — с группами
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu(has_groups: bool = False) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🎬 Мой список")],
        [KeyboardButton(text="➕ Добавить"), KeyboardButton(text="📊 Статистика")],
    ]
    if has_groups:
        kb.append([KeyboardButton(text="👥 Группы")])
    kb.append([KeyboardButton(text="🏠 Главная")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


CATEGORIES = {
    "movie": "🎬 Фильмы",
    "series": "📺 Сериалы",
    "anime": "🌸 Аниме",
    "cartoon": "🧸 Мультфильмы",
    "other": "📦 Прочее",
}

GENRES = [
    "Боевик", "Комедия", "Драма", "Ужасы", "Фантастика",
    "Фэнтези", "Триллер", "Детектив", "Мелодрама", "Приключения",
    "Вестерн", "Мистика", "Криминал", "Военный", "Исторический",
    "Биография", "Спорт", "Музыка", "Документальный", "Семейный",
    "Романтика", "Киберпанк", "Постапокалипсис",
]


def category_keyboard() -> InlineKeyboardMarkup:
    buttons, row = [], []
    for key, label in CATEGORIES.items():
        row.append(InlineKeyboardButton(text=label, callback_data=f"cat:{key}"))
        if len(row) == 2:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def target_keyboard(groups: list, show_personal: bool = True) -> InlineKeyboardMarkup:
    """Выбор: личное или одна из групп"""
    buttons = []
    if show_personal:
        buttons.append([InlineKeyboardButton(text="🔒 Только мне", callback_data="target:personal")])
    for g in groups:
        buttons.append([InlineKeyboardButton(
            text=f"👥 {g.name}", callback_data=f"target:group:{g.id}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def genre_keyboard(selected: list[str] | None = None) -> InlineKeyboardMarkup:
    selected = selected or []
    buttons = []
    for g in GENRES:
        prefix = "✅ " if g in selected else ""
        buttons.append([InlineKeyboardButton(text=f"{prefix}{g}", callback_data=f"genre:{g}")])
    nav_row = []
    if selected:
        nav_row.append(InlineKeyboardButton(text=f"✅ Готово ({len(selected)})", callback_data="genre:done"))
    else:
        nav_row.append(InlineKeyboardButton(text="⏭ Пропустить", callback_data="genre:done"))
    nav_row.append(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    buttons.append(nav_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_add_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Готово", callback_data="confirm_add:yes"),
            InlineKeyboardButton(text="🔄 Заново", callback_data="confirm_add:again"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


def list_context_keyboard(active_group_id: int | None, groups: list):
    """Переключение между личным и групповыми списками. active_group_id=None — личный."""
    buttons = []
    # Личный список
    prefix = "🟢 " if active_group_id is None else ""
    buttons.append([InlineKeyboardButton(text=f"{prefix}🔒 Моё", callback_data="ctx:personal")])
    for g in groups:
        prefix = "🟢 " if active_group_id == g.id else ""
        buttons.append([InlineKeyboardButton(text=f"{prefix}👥 {g.name}", callback_data=f"ctx:group:{g.id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def list_nav_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"list:page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"list:page:{page+1}"))
    buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(text="📋 План", callback_data="list:filter:planned"),
        InlineKeyboardButton(text="👀 Смотрю", callback_data="list:filter:watching"),
    ])
    buttons.append([
        InlineKeyboardButton(text="✅ Просм.", callback_data="list:filter:watched"),
        InlineKeyboardButton(text="📂 Все", callback_data="list:filter:all"),
    ])
    buttons.append([InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def entry_actions_keyboard(entry_id: int, status: str, is_group: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if status == "planned":
        buttons.append([InlineKeyboardButton(text="👀 Начать смотреть", callback_data=f"entry:watch:{entry_id}")])
    elif status == "watching":
        buttons.append([InlineKeyboardButton(text="✅ Просмотрено!", callback_data=f"entry:watched:{entry_id}")])
    if status != "planned":
        buttons.append([InlineKeyboardButton(text="📋 Вернуть в план", callback_data=f"entry:replan:{entry_id}")])
    buttons.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"entry:delete:{entry_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def del_confirm_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"del:yes:{entry_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="del:no"),
        ]
    ])


def rate_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    row, buttons = [], []
    for i in range(1, 11):
        row.append(InlineKeyboardButton(text="⭐" if i == 10 else str(i), callback_data=f"rate:{entry_id}:{i}"))
        if i % 5 == 0:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="⏭ Без оценки", callback_data=f"rate:{entry_id}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_keyboard(group_id: int | None = None) -> InlineKeyboardMarkup:
    prefix = f"stats:{':group:' + str(group_id) if group_id else 'personal'}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Неделя", callback_data=f"{prefix}:week"),
            InlineKeyboardButton(text="📅 Месяц", callback_data=f"{prefix}:month"),
        ],
        [InlineKeyboardButton(text="📅 Всё время", callback_data=f"{prefix}:all")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")],
    ])


def empty_keyboard(in_group: bool = False) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="➕ Добавить первый фильм", callback_data="start_add")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Группы ──

def groups_menu_keyboard(groups: list) -> InlineKeyboardMarkup:
    """Меню управления группами"""
    buttons = []
    for g in groups:
        buttons.append([InlineKeyboardButton(
            text=f"👥 {g.name} (код: {g.invite_code})",
            callback_data=f"grp:open:{g.id}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Создать группу", callback_data="grp:create")])
    buttons.append([InlineKeyboardButton(text="🔗 Войти по коду", callback_data="grp:join")])
    buttons.append([InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def group_detail_keyboard(group_id: int, invite_code: str, member_count: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📋 Смотреть список", callback_data=f"ctx:group:{group_id}")],
        [InlineKeyboardButton(text="➕ Добавить в группу", callback_data=f"grp:add:{group_id}")],
        [InlineKeyboardButton(text="🚪 Покинуть", callback_data=f"grp:leave:{group_id}")],
        [InlineKeyboardButton(text="◀️ К группам", callback_data="grp:list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def del_group_confirm_keyboard(group_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, выйти", callback_data=f"grp:leave_ok:{group_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data="grp:list"),
        ]
    ])