"""
База данных WatchList Bot v2 — с групповыми списками
"""

import datetime
from typing import Optional
from models import User, WatchEntry, WatchGroup, WatchGroupMember, init_db, generate_invite_code

init_db()


# ── Пользователь ──

def get_or_create_user(telegram_id: int, username: str | None = None) -> User:
    user, created = User.get_or_create(
        telegram_id=telegram_id,
        defaults={"username": username}
    )
    if username and user.username != username:
        user.username = username
        user.save()
    return user


# ── Группы ──

def create_group(name: str, creator_id: int) -> WatchGroup:
    """Создать группу, создатель автоматически вступает"""
    code = generate_invite_code()
    # Гарантируем уникальность кода
    while WatchGroup.select().where(WatchGroup.invite_code == code).exists():
        code = generate_invite_code()
    group = WatchGroup.create(name=name, invite_code=code, created_by=creator_id)
    WatchGroupMember.create(group=group, user_telegram_id=creator_id)
    return group


def join_group(invite_code: str, user_id: int) -> Optional[WatchGroup]:
    """Вступить в группу по инвайт-коду. Возвращает None если код неверный."""
    try:
        group = WatchGroup.get(WatchGroup.invite_code == invite_code.strip().upper())
    except WatchGroup.DoesNotExist:
        return None

    _, created = WatchGroupMember.get_or_create(
        group=group,
        user_telegram_id=user_id,
    )
    return group


def leave_group(group_id: int, user_id: int) -> bool:
    """Покинуть группу"""
    deleted = WatchGroupMember.delete().where(
        WatchGroupMember.group_id == group_id,
        WatchGroupMember.user_telegram_id == user_id,
    ).execute()
    # Если в группе никого не осталось — удаляем группу
    if WatchGroupMember.select().where(WatchGroupMember.group_id == group_id).count() == 0:
        WatchGroup.delete_by_id(group_id)
    return deleted > 0


def get_user_groups(user_id: int) -> list[WatchGroup]:
    """Все группы, в которых состоит пользователь"""
    memberships = WatchGroupMember.select().where(
        WatchGroupMember.user_telegram_id == user_id
    )
    return [m.group for m in memberships]


def get_group(group_id: int) -> Optional[WatchGroup]:
    try:
        return WatchGroup.get_by_id(group_id)
    except WatchGroup.DoesNotExist:
        return None


def get_group_members(group_id: int) -> list[int]:
    """Список telegram_id участников группы"""
    return [m.user_telegram_id for m in WatchGroupMember.select().where(
        WatchGroupMember.group_id == group_id
    )]


# ── Добавление ──

def add_entry(
    user_id: int,
    title: str,
    category: str,
    genres: list[str],
    note: str = "",
    group_id: int | None = None,
) -> WatchEntry:
    data = {
        "user": user_id,
        "title": title,
        "category": category,
        "genre": ", ".join(genres),
        "note": note,
    }
    if group_id:
        data["group"] = group_id
    return WatchEntry.create(**data)


def get_entry(entry_id: int) -> Optional[WatchEntry]:
    try:
        return WatchEntry.get_by_id(entry_id)
    except WatchEntry.DoesNotExist:
        return None


# ── Список ──

def get_entries(
    user_id: int,
    status: str = "all",
    category: str = "",
    genre: str = "",
    group_id: int | None = None,
    page: int = 0,
    page_size: int = 15,
) -> tuple[list[WatchEntry], int]:
    """
    Получить записи.
    - group_id=None → личные
    - group_id=123  → группа
    """
    if group_id is None:
        query = WatchEntry.select().where(
            WatchEntry.user == user_id,
            WatchEntry.group.is_null(),
        )
    else:
        # Групповая запись — видна всем участникам группы
        query = WatchEntry.select().where(
            WatchEntry.group_id == group_id,
        )

    if status and status != "all":
        query = query.where(WatchEntry.status == status)
    if category:
        query = query.where(WatchEntry.category == category)
    if genre:
        query = query.where(WatchEntry.genre.contains(genre))

    total = query.count()
    entries = (
        query
        .order_by(WatchEntry.created_at.desc())
        .paginate(page + 1, page_size)
    )
    return list(entries), total


def get_entry_counts(user_id: int, group_id: int | None = None) -> dict:
    """Статистика по статусам"""
    if group_id is None:
        q = WatchEntry.select().where(
            WatchEntry.user == user_id,
            WatchEntry.group.is_null(),
        )
    else:
        q = WatchEntry.select().where(WatchEntry.group_id == group_id)

    total = q.count()
    planned = q.where(WatchEntry.status == "planned").count()
    watching = q.where(WatchEntry.status == "watching").count()
    watched = q.where(WatchEntry.status == "watched").count()

    return {
        "total": total,
        "planned": planned,
        "watching": watching,
        "watched": watched,
    }


def get_category_counts(user_id: int, group_id: int | None = None) -> dict:
    """Статистика по категориям"""
    from collections import Counter
    c = Counter()
    if group_id is None:
        query = WatchEntry.select().where(
            WatchEntry.user == user_id,
            WatchEntry.group.is_null(),
        )
    else:
        query = WatchEntry.select().where(WatchEntry.group_id == group_id)
    for entry in query:
        c[entry.category] += 1
    return dict(c)


def get_watched_history(
    user_id: int,
    period: str = "all",
    group_id: int | None = None,
) -> list[WatchEntry]:
    """История просмотренного"""
    if group_id is None:
        query = WatchEntry.select().where(
            WatchEntry.user == user_id,
            WatchEntry.group.is_null(),
            WatchEntry.status == "watched",
        )
    else:
        query = WatchEntry.select().where(
            WatchEntry.group_id == group_id,
            WatchEntry.status == "watched",
        )

    if period == "week":
        week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        query = query.where(WatchEntry.watched_at >= week_ago)
    elif period == "month":
        month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        query = query.where(WatchEntry.watched_at >= month_ago)

    return list(query.order_by(WatchEntry.watched_at.desc()))


# ── Действия ──

def set_status(entry_id: int, status: str, user_id: int | None = None) -> Optional[WatchEntry]:
    entry = get_entry(entry_id)
    if not entry:
        return None
    entry.status = status
    if status == "watched":
        entry.watched_at = datetime.datetime.now()
        if user_id:
            entry.watched_by = user_id
    entry.save()
    return entry


def set_rating(entry_id: int, rating: int) -> Optional[WatchEntry]:
    entry = get_entry(entry_id)
    if not entry:
        return None
    entry.rating = rating if rating > 0 else None
    entry.save()
    return entry


def delete_entry(entry_id: int, user_id: int | None = None) -> bool:
    """
    Удалить запись. Для личных — только владелец.
    Для групповых — любой участник.
    """
    entry = get_entry(entry_id)
    if not entry:
        return False
    # Проверка прав: личные может удалять только владелец
    if entry.group is None and entry.user != user_id:
        return False
    entry.delete_instance()
    return True


def can_access_entry(entry_id: int, user_id: int) -> bool:
    """Может ли пользователь видеть/редактировать запись?"""
    entry = get_entry(entry_id)
    if not entry:
        return False
    # Личная запись
    if entry.group_id is None:
        return entry.user == user_id
    # Групповая — проверяем членство
    return WatchGroupMember.select().where(
        WatchGroupMember.group_id == entry.group_id,
        WatchGroupMember.user_telegram_id == user_id,
    ).exists()