"""
WatchList Bot v2 — Telegram-бот очереди фильмов/сериалов с групповыми списками
"""

import asyncio, logging, os, sys
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import database as db
import keyboards as kb

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_PROXY = os.getenv("TG_PROXY")
if not BOT_TOKEN:
    log.error("TELEGRAM_BOT_TOKEN не задан!"); sys.exit(1)

session = AiohttpSession(proxy=TG_PROXY) if TG_PROXY else None
bot = Bot(token=BOT_TOKEN, session=session) if session else Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_list_state: dict[str, dict] = {}  # {(user_id:group_id|personal): {status,page}}


class AddEntryStates(StatesGroup):
    waiting_target = State()
    waiting_title = State()
    waiting_category = State()
    waiting_genres = State()
    waiting_note = State()
    confirming = State()

class GroupStates(StatesGroup):
    waiting_name = State()
    waiting_invite = State()

# ── Helpers ──

def ctx_key(user_id: int, gid: int | None) -> str:
    return f"{user_id}:{gid or 'personal'}"

def fmt_line(i: int, e) -> str:
    se = {"planned":"📋","watching":"👀","watched":"✅"}.get(e.status,"📋")
    ce = {"movie":"🎬","series":"📺","anime":"🌸","cartoon":"🧸","other":"📦"}.get(e.category,"📦")
    line = f"{i}. {se}{ce} *{e.title}*"
    if e.status == "watched" and e.rating:
        line += f" ⭐{e.rating}"
    return line


# ── /start & Главная ──

@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    db.get_or_create_user(uid, msg.from_user.username)
    groups = db.get_user_groups(uid)

    text = "🎬 *WatchList Bot*\n\nОчередь фильмов, сериалов, аниме.\nЛичные списки и общие с семьёй/друзьями.\n\n"
    p = db.get_entry_counts(uid, group_id=None)
    text += f"🔒 *Моё:* 📋{p['planned']} 👀{p['watching']} ✅{p['watched']} | {p['total']}\n"
    for g in groups:
        c = db.get_entry_counts(uid, group_id=g.id)
        text += f"👥 *{g.name}:* 📋{c['planned']} 👀{c['watching']} ✅{c['watched']} | {c['total']}\n"
    if p["total"] == 0 and all(db.get_entry_counts(uid, group_id=g.id)["total"] == 0 for g in groups):
        text += "\nПока пусто. Нажми *➕ Добавить*! 👇"

    await msg.answer(text, parse_mode="Markdown", reply_markup=kb.main_menu(has_groups=bool(groups)))


@dp.message(F.text == "🏠 Главная")
@dp.callback_query(F.data == "main_menu")
async def go_home(mc: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    uid = mc.from_user.id
    db.get_or_create_user(uid, mc.from_user.username)
    groups = db.get_user_groups(uid)
    p = db.get_entry_counts(uid, group_id=None)
    text = f"🏠 *Главная*\n\n🔒 Моё: 📋{p['planned']} 👀{p['watching']} ✅{p['watched']} | {p['total']}\n"
    for g in groups:
        c = db.get_entry_counts(uid, group_id=g.id)
        text += f"👥 {g.name}: 📋{c['planned']} 👀{c['watching']} ✅{c['watched']} | {c['total']}\n"
    kb_main = kb.main_menu(has_groups=bool(groups))
    if isinstance(mc, CallbackQuery):
        await mc.message.edit_text(text, parse_mode="Markdown", reply_markup=kb_main)
    else:
        await mc.answer(text, parse_mode="Markdown", reply_markup=kb_main)


# ── Добавление ──

@dp.message(F.text == "➕ Добавить")
@dp.callback_query(F.data == "start_add")
async def start_add(mc: Message | CallbackQuery, state: FSMContext):
    uid = mc.from_user.id
    groups = db.get_user_groups(uid)
    if groups:
        await state.set_state(AddEntryStates.waiting_target)
        text = "Куда добавить — только себе или в общий список?"
        if isinstance(mc, CallbackQuery):
            await mc.message.edit_text(text, reply_markup=kb.target_keyboard(groups))
        else:
            await mc.answer(text, reply_markup=kb.target_keyboard(groups))
    else:
        await state.update_data(target_group=None)
        await state.set_state(AddEntryStates.waiting_title)
        text = "🎬 *Добавить новое*\n\nВведи *название*:"
        if isinstance(mc, CallbackQuery):
            await mc.message.edit_text(text, parse_mode="Markdown")
        else:
            await mc.answer(text, parse_mode="Markdown")


@dp.callback_query(AddEntryStates.waiting_target)
async def process_target(call: CallbackQuery, state: FSMContext):
    if call.data.startswith("target:personal"):
        await state.update_data(target_group=None, target_label="🔒 Личное")
    elif call.data.startswith("target:group:"):
        gid = int(call.data.split(":")[2])
        group = db.get_group(gid)
        await state.update_data(target_group=gid, target_label=f"👥 {group.name}" if group else "👥 Группа")
    elif call.data == "cancel":
        await state.clear(); await call.message.edit_text("❌ Отменено.", reply_markup=kb.main_menu()); return
    else:
        return
    await state.set_state(AddEntryStates.waiting_title)
    label = (await state.get_data()).get("target_label", "")
    await call.message.edit_text(f"🎬 *Добавить → {label}*\n\nВведи *название*:", parse_mode="Markdown")


@dp.message(AddEntryStates.waiting_title)
async def process_title(msg: Message, state: FSMContext):
    title = msg.text.strip()
    if len(title) < 1 or len(title) > 500:
        await msg.answer("⚠️ Название от 1 до 500 символов:"); return
    await state.update_data(title=title)
    await state.set_state(AddEntryStates.waiting_category)
    await msg.answer(f"📌 *{title}*\n\nВыбери *категорию*:", parse_mode="Markdown", reply_markup=kb.category_keyboard())


@dp.callback_query(AddEntryStates.waiting_category)
async def process_category(call: CallbackQuery, state: FSMContext):
    if call.data.startswith("cat:"):
        category = call.data.split(":")[1]
        await state.update_data(category=category, selected_genres=[])
        await state.set_state(AddEntryStates.waiting_genres)
        label = kb.CATEGORIES.get(category, category)
        await call.message.edit_text(f"📌 *{label}*\n\nВыбери *жанры* (можно несколько):", parse_mode="Markdown", reply_markup=kb.genre_keyboard())
    elif call.data == "cancel":
        await state.clear(); await call.message.edit_text("❌ Отменено.", reply_markup=kb.main_menu())


@dp.callback_query(AddEntryStates.waiting_genres)
async def process_genres(call: CallbackQuery, state: FSMContext):
    if call.data.startswith("genre:"):
        genre = call.data.split(":")[1]
        if genre == "done":
            await state.set_state(AddEntryStates.waiting_note)
            data = await state.get_data()
            genres_str = ", ".join(data.get("selected_genres", []))
            cat_label = kb.CATEGORIES.get(data.get("category", ""), "")
            text = f"📌 *{data['title']}*\n📂 {cat_label}\n🏷 {genres_str or '—'}\n\nХочешь добавить *заметку*?\nНапиши текст или /skip"
            await call.message.edit_text(text, parse_mode="Markdown")
        else:
            data = await state.get_data()
            selected = data.get("selected_genres", [])
            if genre in selected: selected.remove(genre)
            else: selected.append(genre)
            await state.update_data(selected_genres=selected)
            await call.message.edit_reply_markup(reply_markup=kb.genre_keyboard(selected))
    elif call.data == "cancel":
        await state.clear(); await call.message.edit_text("❌ Отменено.", reply_markup=kb.main_menu())


@dp.message(AddEntryStates.waiting_note)
async def process_note(msg: Message, state: FSMContext):
    await state.update_data(note=msg.text.strip() if msg.text else "")
    await _show_confirm(msg, state)


@dp.message(AddEntryStates.waiting_note, Command("skip"))
async def skip_note(msg: Message, state: FSMContext):
    await state.update_data(note="")
    await _show_confirm(msg, state)


async def _show_confirm(msg: Message, state: FSMContext):
    data = await state.get_data()
    cl = kb.CATEGORIES.get(data.get("category",""),"")
    gs = ", ".join(data.get("selected_genres",[]))
    t = f"✅ *Проверь:*\n\n🎬 *{data['title']}*\n📂 {cl}\n🏷 {gs or '—'}\n📍 {data.get('target_label','🔒 Личное')}\n"
    if data.get("note"): t += f"💬 {data['note']}\n"
    await state.set_state(AddEntryStates.confirming)
    await msg.answer(t, parse_mode="Markdown", reply_markup=kb.confirm_add_keyboard())


@dp.callback_query(AddEntryStates.confirming)
async def confirm_add(call: CallbackQuery, state: FSMContext):
    if call.data == "confirm_add:yes":
        data = await state.get_data()
        db.add_entry(user_id=call.from_user.id, title=data["title"], category=data["category"],
                     genres=data.get("selected_genres",[]), note=data.get("note",""),
                     group_id=data.get("target_group"))
        await call.message.edit_text(f"✅ *{data['title']}* добавлен! 🎉", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Ещё", callback_data="start_add"),
                 InlineKeyboardButton(text="🎬 Список", callback_data="goto_list")],
                [InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")]]))
        await state.clear()
    elif call.data == "confirm_add:again":
        await state.set_state(AddEntryStates.waiting_title)
        await call.message.edit_text("🔄 Давай заново.\n\nВведи *название*:", parse_mode="Markdown")
    elif call.data == "cancel":
        await state.clear(); await call.message.edit_text("❌ Отменено.", reply_markup=kb.main_menu())


# ── Список ──

@dp.message(F.text == "🎬 Мой список")
@dp.callback_query(F.data == "goto_list")
async def show_list(mc: Message | CallbackQuery):
    uid = mc.from_user.id; groups = db.get_user_groups(uid)
    if groups:
        text = "Какой список смотреть?"
        if isinstance(mc, CallbackQuery): await mc.message.edit_text(text, reply_markup=kb.list_context_keyboard(None, groups))
        else: await mc.answer(text, reply_markup=kb.list_context_keyboard(None, groups))
    else:
        await show_list_ctx(mc, group_id=None, status="all", page=0)


@dp.callback_query(F.data.startswith("ctx:"))
async def switch_context(call: CallbackQuery):
    uid = call.from_user.id
    if call.data == "ctx:personal":
        await show_list_ctx(call, group_id=None, status="all", page=0)
    elif call.data.startswith("ctx:group:"):
        gid = int(call.data.split(":")[2])
        if uid not in db.get_group_members(gid):
            await call.answer("❌ Ты не в этой группе", show_alert=True); return
        await show_list_ctx(call, group_id=gid, status="all", page=0)


async def show_list_ctx(mc: Message | CallbackQuery, group_id: int | None, status: str, page: int, edit: bool = True):
    uid = mc.from_user.id; groups = db.get_user_groups(uid)
    key = ctx_key(uid, group_id); user_list_state[key] = {"status": status, "page": page}

    entries, total = db.get_entries(uid, status=status, group_id=group_id, page=page)
    header = "🔒 *Мой список*" if group_id is None else f"👥 *{(db.get_group(group_id) or type('x',(),{'name':'?'})()).name}*"

    if not entries:
        text = f"{header}\n\n📭 Пока пусто."
        k = kb.empty_keyboard()
        if groups:
            k.inline_keyboard = kb.list_context_keyboard(group_id, groups).inline_keyboard + k.inline_keyboard
        if edit and isinstance(mc, CallbackQuery): await mc.message.edit_text(text, parse_mode="Markdown", reply_markup=k)
        else: await mc.answer(text, parse_mode="Markdown", reply_markup=k)
        return

    total_pages = max(1, (total + 14) // 15)
    text = f"{header} | Всего: {total}\n\n"
    for i, e in enumerate(entries, page * 15 + 1): text += fmt_line(i, e) + "\n"

    # Num buttons
    nb = []; row = []
    for i, e in enumerate(entries, page * 15 + 1):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"entry:open:{e.id}"))
        if len(row) == 5: nb.append(row); row = []
    if row: nb.append(row)

    # Context + nav
    cb = list(kb.list_context_keyboard(group_id, groups).inline_keyboard) if groups else []
    cb.extend(kb.list_nav_keyboard(page, total_pages).inline_keyboard)

    fk = InlineKeyboardMarkup(inline_keyboard=nb + cb)
    if edit and isinstance(mc, CallbackQuery): await mc.message.edit_text(text, parse_mode="Markdown", reply_markup=fk)
    else: await mc.answer(text, parse_mode="Markdown", reply_markup=fk)


@dp.callback_query(F.data.startswith("list:page:"))
async def list_page(call: CallbackQuery):
    page = int(call.data.split(":")[2]); uid = call.from_user.id
    for k, s in user_list_state.items():
        if k.startswith(f"{uid}:"):
            key = k.split(":",1)[1]; gid = None if key == "personal" else int(key)
            s["page"] = page; await show_list_ctx(call, group_id=gid, status=s.get("status","all"), page=page); return
    await show_list_ctx(call, group_id=None, status="all", page=page)


@dp.callback_query(F.data.startswith("list:filter:"))
async def list_filter(call: CallbackQuery):
    status = call.data.split(":")[2]; uid = call.from_user.id
    for k, s in user_list_state.items():
        if k.startswith(f"{uid}:"):
            key = k.split(":",1)[1]; gid = None if key == "personal" else int(key)
            s["status"] = status; s["page"] = 0
            await show_list_ctx(call, group_id=gid, status=status, page=0); return
    await show_list_ctx(call, group_id=None, status=status, page=0)


@dp.callback_query(F.data == "back_to_list")
async def back_to_list(call: CallbackQuery):
    uid = call.from_user.id
    for k, s in user_list_state.items():
        if k.startswith(f"{uid}:"):
            key = k.split(":",1)[1]; gid = None if key == "personal" else int(key)
            await show_list_ctx(call, group_id=gid, status=s.get("status","all"), page=s.get("page",0)); return
    await show_list_ctx(call, group_id=None, status="all", page=0)


# ── Действия с записью ──

@dp.callback_query(F.data.startswith("entry:open:"))
async def entry_open(call: CallbackQuery):
    eid = int(call.data.split(":")[2]); entry = db.get_entry(eid)
    if not entry or not db.can_access_entry(eid, call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True); return
    sl = {"planned":"📋 В планах","watching":"👀 Смотрю","watched":"✅ Просмотрено"}
    cl = {"movie":"🎬 Фильм","series":"📺 Сериал","anime":"🌸 Аниме","cartoon":"🧸 Мультфильм","other":"📦 Прочее"}
    is_group = entry.group_id is not None
    text = f"🎬 *{entry.title}*\n\n📂 {cl.get(entry.category,entry.category)}\n📌 {sl.get(entry.status,entry.status)}\n"
    if entry.genre: text += f"🏷 {entry.genre}\n"
    if entry.note: text += f"💬 {entry.note}\n"
    if is_group: text += f"👤 Добавил: {entry.user}\n"
    if entry.watched_at:
        text += f"📅 Просмотрено: {entry.watched_at.strftime('%d.%m.%Y')}\n"
        if entry.watched_by: text += f"👀 Отметил: {entry.watched_by}\n"
    if entry.rating: text += f"⭐ {entry.rating}/10\n"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.entry_actions_keyboard(eid, entry.status, is_group))


@dp.callback_query(F.data.startswith("entry:watch:"))
async def e_watch(call: CallbackQuery):
    eid = int(call.data.split(":")[2]); entry = db.get_entry(eid)
    if not entry or not db.can_access_entry(eid, call.from_user.id): await call.answer("❌ Нет доступа", show_alert=True); return
    entry = db.set_status(eid, "watching")
    await call.message.edit_text(f"👀 *{entry.title}* — начали смотреть!", parse_mode="Markdown",
        reply_markup=kb.entry_actions_keyboard(eid, entry.status, entry.group_id is not None))


@dp.callback_query(F.data.startswith("entry:watched:"))
async def e_watched(call: CallbackQuery):
    eid = int(call.data.split(":")[2]); entry = db.get_entry(eid)
    if not entry or not db.can_access_entry(eid, call.from_user.id): await call.answer("❌ Нет доступа", show_alert=True); return
    entry = db.set_status(eid, "watched", user_id=call.from_user.id)
    await call.message.edit_text(f"✅ *{entry.title}* — просмотрено!\n\nОцени от 1 до 10:", parse_mode="Markdown",
        reply_markup=kb.rate_keyboard(eid))


@dp.callback_query(F.data.startswith("entry:replan:"))
async def e_replan(call: CallbackQuery):
    eid = int(call.data.split(":")[2]); entry = db.get_entry(eid)
    if not entry or not db.can_access_entry(eid, call.from_user.id): await call.answer("❌ Нет доступа", show_alert=True); return
    entry = db.set_status(eid, "planned")
    await call.message.edit_text(f"📋 *{entry.title}* — вернули в план!", parse_mode="Markdown",
        reply_markup=kb.entry_actions_keyboard(eid, entry.status, entry.group_id is not None))


@dp.callback_query(F.data.startswith("entry:delete:"))
async def e_delete(call: CallbackQuery):
    eid = int(call.data.split(":")[2])
    if not db.can_access_entry(eid, call.from_user.id): await call.answer("❌ Нет доступа", show_alert=True); return
    await call.message.edit_text("❓ *Точно удалить?*", parse_mode="Markdown", reply_markup=kb.del_confirm_keyboard(eid))


@dp.callback_query(F.data.startswith("del:yes:"))
async def del_yes(call: CallbackQuery):
    eid = int(call.data.split(":")[2])
    db.delete_entry(eid, user_id=call.from_user.id)
    await go_home(call, None)


@dp.callback_query(F.data == "del:no")
async def del_no(call: CallbackQuery):
    await go_home(call, None)


@dp.callback_query(F.data.startswith("rate:"))
async def e_rate(call: CallbackQuery):
    _, eid_s, r_s = call.data.split(":")[:3]; eid, r = int(eid_s), int(r_s)
    db.set_rating(eid, r); entry = db.get_entry(eid)
    text = f"⭐ *{entry.title}* — {r}/10!" if r > 0 else f"✅ *{entry.title}* — без оценки."
    await call.message.edit_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎬 К списку", callback_data="goto_list")],
            [InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")]]))


# ── Группы ──

@dp.message(F.text == "👥 Группы")
@dp.callback_query(F.data == "grp:list")
async def groups_menu(mc: Message | CallbackQuery):
    uid = mc.from_user.id; groups = db.get_user_groups(uid)
    if not groups:
        text = "👥 *Группы*\n\nУ тебя пока нет групп.\nСоздай общий список для семьи или друзей!"
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать группу", callback_data="grp:create")],
            [InlineKeyboardButton(text="🔗 Войти по коду", callback_data="grp:join")],
            [InlineKeyboardButton(text="🏠 Главная", callback_data="main_menu")]])
    else:
        text = "👥 *Твои группы*\n\n"
        for g in groups:
            cnt = db.get_entry_counts(uid, group_id=g.id)["total"]
            m = db.get_group_members(g.id)
            text += f"• *{g.name}* — {cnt} записей, {len(m)} чел.\n  Код: `{g.invite_code}`\n"
        text += "\nПоделись кодом с тем, кого хочешь пригласить 👆"
        buttons = kb.groups_menu_keyboard(groups)
    if isinstance(mc, CallbackQuery): await mc.message.edit_text(text, parse_mode="Markdown", reply_markup=buttons)
    else: await mc.answer(text, parse_mode="Markdown", reply_markup=buttons)


@dp.callback_query(F.data == "grp:create")
async def grp_create_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(GroupStates.waiting_name)
    await call.message.edit_text("➕ *Новая группа*\n\nПридумай название:", parse_mode="Markdown")


@dp.message(GroupStates.waiting_name)
async def grp_create_done(msg: Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 1 or len(name) > 200: await msg.answer("⚠️ Название от 1 до 200 символов:"); return
    group = db.create_group(name, msg.from_user.id)
    await state.clear()
    text = f"✅ Группа *{name}* создана!\n\n🔑 Код для входа: `{group.invite_code}`\n\nОтправь этот код тому, кого хочешь пригласить."
    await msg.answer(text, parse_mode="Markdown", reply_markup=kb.group_detail_keyboard(group.id, group.invite_code, 1))


@dp.callback_query(F.data == "grp:join")
async def grp_join_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(GroupStates.waiting_invite)
    await call.message.edit_text("🔗 Введи *код приглашения* (8 символов):", parse_mode="Markdown")


@dp.message(GroupStates.waiting_invite)
async def grp_join_done(msg: Message, state: FSMContext):
    code = msg.text.strip()
    group = db.join_group(code, msg.from_user.id)
    if group is None: await msg.answer("❌ Неверный код. Попробуй ещё раз или /cancel"); return
    await state.clear()
    m = db.get_group_members(group.id)
    await msg.answer(f"✅ Ты в группе *{group.name}*! 🎉\n👥 Участников: {len(m)}", parse_mode="Markdown",
                     reply_markup=kb.group_detail_keyboard(group.id, group.invite_code, len(m)))
    await msg.answer("Меню обновлено 👇", reply_markup=kb.main_menu(has_groups=True))


@dp.callback_query(F.data.startswith("grp:open:"))
async def grp_open(call: CallbackQuery):
    gid = int(call.data.split(":")[2]); group = db.get_group(gid)
    if not group: await call.answer("❌ Группа не найдена", show_alert=True); return
    m = db.get_group_members(gid); cnt = db.get_entry_counts(call.from_user.id, group_id=gid)["total"]
    text = f"👥 *{group.name}*\n\n📊 Записей: {cnt}\n👤 Участников: {len(m)}\n🔑 Код: `{group.invite_code}`"
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.group_detail_keyboard(gid, group.invite_code, len(m)))


@dp.callback_query(F.data.startswith("grp:add:"))
async def grp_add(call: CallbackQuery, state: FSMContext):
    gid = int(call.data.split(":")[2]); group = db.get_group(gid)
    await state.update_data(target_group=gid, target_label=f"👥 {group.name}")
    await state.set_state(AddEntryStates.waiting_title)
    await call.message.edit_text(f"🎬 *Добавить → 👥 {group.name}*\n\nВведи *название*:", parse_mode="Markdown")


@dp.callback_query(F.data.startswith("grp:leave:"))
async def grp_leave_confirm(call: CallbackQuery):
    gid = int(call.data.split(":")[2]); group = db.get_group(gid)
    if not group: await call.answer("❌ Не найдено", show_alert=True); return
    await call.message.edit_text(f"❓ Выйти из группы *{group.name}*?\nТвои личные записи сохранятся.", parse_mode="Markdown",
                                 reply_markup=kb.del_group_confirm_keyboard(gid))


@dp.callback_query(F.data.startswith("grp:leave_ok:"))
async def grp_leave_ok(call: CallbackQuery):
    gid = int(call.data.split(":")[2]); db.leave_group(gid, call.from_user.id)
    await call.answer("Вышел из группы"); await groups_menu(call)


# ── Статистика ──

@dp.message(F.text == "📊 Статистика")
async def cmd_stats(msg: Message):
    uid = msg.from_user.id; groups = db.get_user_groups(uid)
    text = _stats_text(uid, group_id=None, label="🔒 Личное")
    if groups:
        text += "\n👇 Выбери период (личное):"
        await msg.answer(text, parse_mode="Markdown", reply_markup=kb.stats_keyboard(group_id=None))
    else:
        await msg.answer(text, parse_mode="Markdown", reply_markup=kb.stats_keyboard(group_id=None))


def _stats_text(uid: int, group_id: int | None, label: str) -> str:
    counts = db.get_entry_counts(uid, group_id=group_id)
    cat = db.get_category_counts(uid, group_id=group_id)
    cl = {"movie":"🎬 Фильмы","series":"📺 Сериалы","anime":"🌸 Аниме","cartoon":"🧸 Мультфильмы","other":"📦 Прочее"}
    ct = "\n".join(f"{cl.get(c,c)}: {n}" for c, n in sorted(cat.items(), key=lambda x:-x[1]))
    return (f"📊 *Статистика — {label}*\n\n"
            f"📋 В планах: {counts['planned']}\n"
            f"👀 Смотрю: {counts['watching']}\n"
            f"✅ Просмотрено: {counts['watched']}\n"
            f"━━━━━━━━━━━━\nВсего: {counts['total']}\n\n"
            f"*По категориям:*\n{ct}")


@dp.callback_query(F.data.startswith("stats:"))
async def stats_period(call: CallbackQuery):
    parts = call.data.split(":")
    # stats:personal:week  OR  stats:group:123:week
    scope = parts[1]
    gid = None
    if scope == "group":
        gid = int(parts[2])
        period = parts[3]
    else:
        period = parts[1]

    uid = call.from_user.id
    history = db.get_watched_history(uid, period, group_id=gid)
    pl = {"week":"За неделю","month":"За месяц","all":"За всё время"}

    if not history:
        await call.message.edit_text(f"📭 Ничего не просмотрено ({pl.get(period,period)}).",
                                     reply_markup=kb.stats_keyboard(group_id=gid))
        return

    text = f"✅ *Просмотрено — {pl.get(period,period)}:*\n\n"
    for e in history:
        r = f" ⭐{e.rating}/10" if e.rating else ""
        text += f"• {e.title}{r}\n  📅 {e.watched_at.strftime('%d.%m.%Y') if e.watched_at else '—'}\n"

    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.stats_keyboard(group_id=gid))


# ── Misc ──

@dp.callback_query(F.data == "noop")
async def noop(call: CallbackQuery): await call.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_action(call: CallbackQuery, state: FSMContext):
    await state.clear(); await call.message.edit_text("❌ Отменено.", reply_markup=kb.main_menu())


@dp.message()
async def fallback(msg: Message, state: FSMContext):
    if await state.get_state() is None:
        await msg.answer("Используй кнопки меню 👇", reply_markup=kb.main_menu(has_groups=has_groups(msg.from_user.id)))


# ── Запуск ──

async def main():
    log.info("🚀 WatchList Bot v2 запущен (с группами)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())