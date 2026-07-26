import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Destinataires
EMAIL_DESTINATAIRES = ["cep.uv1@ahs-fc.fr", "wiedmannguillian@gmail.com"]

# États
SELECT_TYPE, ENTER_MOTIF, ENTER_DATE, ENTER_TIME, ADD_ANOTHER, CONFIRM = range(6)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def send_email(recap_text: str) -> bool:
    """Envoie le récapitulatif aux deux adresses"""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ", ".join(EMAIL_DESTINATAIRES)
    msg["Subject"] = f"Nouveaux RDV - {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    body = f"""Bonjour,

Voici le récapitulatif des rendez-vous :

{recap_text}

---
Envoyé automatiquement via le bot Telegram.
"""
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email : {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bonjour !\nUtilise /nouveau pour ajouter des rendez-vous."
    )


async def nouveau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rdvs"] = []
    context.user_data["current"] = {}

    keyboard = [
        [InlineKeyboardButton("Rdv kiné", callback_data="type_kine")],
        [InlineKeyboardButton("Rdv Milo", callback_data="type_milo")],
        [InlineKeyboardButton("Autre", callback_data="type_autre")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Quel type de rendez-vous souhaites-tu ajouter ?",
        reply_markup=reply_markup
    )
    return SELECT_TYPE


async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "type_kine":
        context.user_data["current"]["type"] = "Rdv kiné"
        await query.edit_message_text(
            "Type sélectionné : **Rdv kiné**\n\nIndique la date (format : 05/04/2026)",
            parse_mode="Markdown"
        )
        return ENTER_DATE

    elif query.data == "type_milo":
        context.user_data["current"]["type"] = "Rdv Milo"
        await query.edit_message_text(
            "Type sélectionné : **Rdv Milo**\n\nIndique la date (format : 05/04/2026)",
            parse_mode="Markdown"
        )
        return ENTER_DATE

    elif query.data == "type_autre":
        await query.edit_message_text("Tu as choisi **Autre**.\n\nÉcris le motif du rendez-vous :")
        return ENTER_MOTIF


async def enter_motif(update: Update, context: ContextTypes.DEFAULT_TYPE):
    motif = update.message.text.strip()
    context.user_data["current"]["type"] = f"Autre : {motif}"
    await update.message.reply_text("Motif enregistré.\n\nIndique la date (format : 05/04/2026)")
    return ENTER_DATE


async def enter_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()

    try:
        datetime.strptime(date_text, "%d/%m/%Y")
    except ValueError:
        await update.message.reply_text("Format incorrect. Utilise le format : 05/04/2026")
        return ENTER_DATE

    context.user_data["current"]["date"] = date_text
    await update.message.reply_text("Date enregistrée.\n\nIndique l’heure (format : 15h30)")
    return ENTER_TIME


async def enter_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip().lower()

    if "h" not in time_text:
        await update.message.reply_text("Format incorrect. Utilise le format : 15h30")
        return ENTER_TIME

    context.user_data["current"]["heure"] = time_text
    context.user_data["rdvs"].append(context.user_data["current"].copy())
    context.user_data["current"] = {}

    keyboard = [
        [InlineKeyboardButton("✅ Oui", callback_data="add_yes")],
        [InlineKeyboardButton("❌ Non", callback_data="add_no")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Rendez-vous ajouté !\n\nAs-tu un autre rendez-vous à ajouter ?",
        reply_markup=reply_markup
    )
    return ADD_ANOTHER


async def add_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_yes":
        keyboard = [
            [InlineKeyboardButton("Rdv kiné", callback_data="type_kine")],
            [InlineKeyboardButton("Rdv Milo", callback_data="type_milo")],
            [InlineKeyboardButton("Autre", callback_data="type_autre")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Quel type de rendez-vous souhaites-tu ajouter ?",
            reply_markup=reply_markup
        )
        return SELECT_TYPE

    else:
        rdvs = context.user_data.get("rdvs", [])
        if not rdvs:
            await query.edit_message_text("Aucun rendez-vous enregistré.")
            return ConversationHandler.END

        recap = ""
        for i, rdv in enumerate(rdvs, 1):
            recap += f"{i}. {rdv['type']}\n   📅 {rdv['date']} à {rdv['heure']}\n\n"

        keyboard = [
            [InlineKeyboardButton("✅ Valider et envoyer", callback_data="confirm_yes")],
            [InlineKeyboardButton("❌ Annuler", callback_data="confirm_no")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📋 **Récapitulatif des rendez-vous :**\n\n{recap}"
            "Veux-tu valider et envoyer les emails ?",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.edit_message_text("Opération annulée.")
        context.user_data.clear()
        return ConversationHandler.END

    rdvs = context.user_data.get("rdvs", [])
    recap = ""
    for i, rdv in enumerate(rdvs, 1):
        recap += f"{i}. {rdv['type']} — {rdv['date']} à {rdv['heure']}\n"

    success = send_email(recap)

    if success:
        await query.edit_message_text(
            "✅ Emails envoyés avec succès à :\n"
            "• cep.uv1@ahs-fc.fr\n"
            "• wiedmannguillian@gmail.com"
        )
    else:
        await query.edit_message_text(
            "❌ Erreur lors de l’envoi des emails.\n"
            "Vérifie ta clé Gmail et ton adresse dans le fichier .env"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Opération annulée.")
    context.user_data.clear()
    return ConversationHandler.END


def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("nouveau", nouveau)],
        states={
            SELECT_TYPE: [CallbackQueryHandler(select_type, pattern="^type_")],
            ENTER_MOTIF: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_motif)],
            ENTER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            ENTER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_time)],
            ADD_ANOTHER: [CallbackQueryHandler(add_another, pattern="^add_")],
            CONFIRM: [CallbackQueryHandler(confirm, pattern="^confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)

    print("Bot démarré...")
    application.run_polling()


if __name__ == "__main__":
    main()
