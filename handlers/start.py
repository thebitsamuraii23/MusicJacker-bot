"""Handlers related to /start and language selection."""
from __future__ import annotations

import json
from typing import Dict

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import LANG_CODES, LANG_INLINE_BUTTONS, LANGUAGES, USER_LANGS_FILE
from utils.logger import get_logger

logger = get_logger(__name__)

user_langs: Dict[int, str] = {}


def load_user_langs() -> None:
    """Load saved user languages from disk if available."""
    global user_langs
    try:
        with open(USER_LANGS_FILE, 'r', encoding='utf-8') as fh:
            loaded = json.load(fh)
            user_langs = {int(k): v for k, v in loaded.items()}
    except FileNotFoundError:
        user_langs = {}
    except json.JSONDecodeError:
        logger.warning("Failed to decode %s. Starting with empty language map.", USER_LANGS_FILE)
        user_langs = {}


def save_user_langs() -> None:
    """Persist user language preferences to disk."""
    with open(USER_LANGS_FILE, 'w', encoding='utf-8') as fh:
        json.dump(user_langs, fh)


def get_user_lang(user_id: int) -> str:
    """Return stored language for user or fallback to Russian."""
    lang = user_langs.get(user_id)
    if lang in LANGUAGES:
        return lang
    return 'ru'


def _build_inline_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for button in LANG_INLINE_BUTTONS:
        row.append(button)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send inline buttons to let user pick a language."""
    logger.info("User %s requested language choice.", update.effective_user.id)
    user_id = update.effective_user.id
    lang = get_user_lang(user_id)
    texts = LANGUAGES.get(lang, LANGUAGES['ru'])
    await update.message.reply_text(
        texts.get('choose_lang', LANGUAGES['ru']['choose_lang']),
        reply_markup=_build_inline_keyboard(),
    )


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle legacy reply keyboard language selection."""
    lang_name = update.message.text
    lang_code = LANG_CODES.get(lang_name)
    user_id = update.effective_user.id
    if lang_code:
        user_langs[user_id] = lang_code
        save_user_langs()
        logger.info("User %s set language to %s.", user_id, lang_code)
        await update.message.reply_text(LANGUAGES[lang_code]['start'])
        return

    logger.warning("User %s sent invalid language selection: %s.", user_id, lang_name)
    current_lang = get_user_lang(user_id)
    texts = LANGUAGES.get(current_lang, LANGUAGES['ru'])
    await update.message.reply_text(texts.get('choose_lang', 'Please choose a language from the keyboard.'))


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process inline language button presses."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    lang_code = None
    if query.data and query.data.startswith('lang_'):
        lang_code = query.data.split('_', 1)[1]

    if not lang_code or lang_code not in LANGUAGES:
        current_lang = get_user_lang(user_id)
        texts = LANGUAGES.get(current_lang, LANGUAGES['ru'])
        try:
            await query.edit_message_text(texts.get('choose_lang', 'Please choose a language.'))
        except Exception:
            pass
        return

    user_langs[user_id] = lang_code
    save_user_langs()
    logger.info("User %s set language (inline) to %s.", user_id, lang_code)
    try:
        await query.edit_message_text(LANGUAGES[lang_code]['start'])
    except Exception:
        try:
            await context.bot.send_message(chat_id=user_id, text=LANGUAGES[lang_code]['start'])
        except Exception:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for /start command."""
    logger.info("User %s issued /start command.", update.effective_user.id)
    await choose_language(update, context)


def register(application: Application) -> None:
    """Register start and language handlers with the application."""
    load_user_langs()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('language', choose_language))
    application.add_handler(CommandHandler('languages', choose_language))
    application.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANG_CODES.keys())})$"), set_language))
    application.add_handler(CallbackQueryHandler(language_callback, pattern=r'^lang_'))
