"""
Модели БД для WatchList Bot v2 — с групповыми списками
"""

import datetime
import uuid
from peewee import SqliteDatabase, Model, CharField, IntegerField, DateTimeField, TextField, ForeignKeyField

DB_PATH = "data/watchlist.db"

db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    telegram_id = IntegerField(unique=True, index=True)
    username = CharField(max_length=255, null=True)
    created_at = DateTimeField(default=datetime.datetime.now)


class WatchGroup(BaseModel):
    """Группа пользователей с общим списком"""
    name = CharField(max_length=200)
    invite_code = CharField(max_length=12, unique=True, index=True)  # короткий код для входа
    created_by = IntegerField(index=True)  # telegram_id создателя
    created_at = DateTimeField(default=datetime.datetime.now)


class WatchGroupMember(BaseModel):
    """Участник группы"""
    group = ForeignKeyField(WatchGroup, backref="members", on_delete="CASCADE")
    user_telegram_id = IntegerField(index=True)
    joined_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        indexes = (
            (("group", "user_telegram_id"), True),  # unique together
        )


class WatchEntry(BaseModel):
    """Один фильм/сериал/аниме в очереди"""
    user = IntegerField(index=True)  # telegram_id создателя
    group = ForeignKeyField(WatchGroup, null=True, backref="entries", on_delete="CASCADE")  # NULL = личное
    title = CharField(max_length=500)
    category = CharField(max_length=50)  # movie | series | anime | cartoon | other
    genre = CharField(max_length=200, default="")  # жанры через запятую
    status = CharField(max_length=20, default="planned")  # planned | watching | watched
    note = TextField(default="")  # заметка
    created_at = DateTimeField(default=datetime.datetime.now)
    watched_at = DateTimeField(null=True)
    watched_by = IntegerField(null=True)  # кто отметил просмотренным
    rating = IntegerField(null=True)  # оценка от 1 до 10 после просмотра


def init_db():
    db.connect()
    db.create_tables([User, WatchGroup, WatchGroupMember, WatchEntry], safe=True)
    db.close()


def generate_invite_code() -> str:
    """Генерация короткого читаемого кода (8 символов)"""
    return uuid.uuid4().hex[:8].upper()