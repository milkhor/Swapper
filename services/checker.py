import asyncio
import logging
from aiogram import Bot

from database.db import get_active_swaps, update_swap_status, update_swap_payment_details
from services.fixedfloat import get_exchange
from services.order_details import extract_payment_details
from config import PUBLIC_CHANNEL_ID, PRIVATE_CHANNEL_ID # Добавили импорты

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 180  # 3 минуты

STATUS_MESSAGES = {
    "waiting":    "⏳ Waiting for incoming transaction...",
    "confirming": "🔄 Transaction found, waiting for network confirmation...",
    "exchanging": "💱 Exchange in progress...",
    "sending":    "📤 Sending to your wallet...",
    "finished":   "✅ Exchange completed! Coins sent to your wallet.",
    "failed":     "❌ Exchange failed. Type /start to try again.",
    "refunded":   "↩️ Funds returned to the source address.",
    "expired":    "⌛ Exchange expired. Type /start to create a new one.",
}

NOTIFY_ON = {"confirming", "exchanging", "sending", "finished", "failed", "refunded", "expired"}

async def check_swaps(bot: Bot):
    """Background task — checks active swaps every 3 minutes."""
    logger.info("Background swap checker started")
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        try:
            swaps = await get_active_swaps()
            if not swaps:
                continue

            for swap in swaps:
                try:
                    # Orders without a token predate the FixedFloat migration and
                    # cannot be queried — skip instead of hitting the API each cycle.
                    if not swap.get("order_token"):
                        continue

                    result = await get_exchange(swap["exchange_id"], swap["order_token"])
                    if not result:
                        continue

                    new_status = result.get("status")
                    address_from, payment_url = extract_payment_details(result)
                    await update_swap_payment_details(
                        swap["exchange_id"],
                        address_from=address_from,
                        payment_url=payment_url,
                    )

                    if not new_status or new_status == swap["status"]:
                        continue

                    # 1. Обновляем БД
                    await update_swap_status(swap["exchange_id"], new_status)
                    
                    # 2. Логика уведомлений в КАНАЛЫ
                    # Приватный канал для админа (любое изменение статуса)
                    if PRIVATE_CHANNEL_ID:
                        try:
                            await bot.send_message(
                                int(PRIVATE_CHANNEL_ID),
                                f"🔔 <b>Status Update</b>\n"
                                f"ID: <code>{swap['exchange_id']}</code>\n"
                                f"User: <code>{swap['user_id']}</code>\n"
                                f"Status: <code>{swap['status']}</code> ➡️ <b>{new_status}</b>"
                            )
                        except Exception as e:
                            logger.error(f"Error sending to Private Channel: {e}")

                    # Публичный канал (только при успехе)
                    if new_status == "finished" and PUBLIC_CHANNEL_ID:
                        try:
                            cur_from = swap['currency_from'].split('_')[0].upper()
                            cur_to = swap['currency_to'].split('_')[0].upper()
                            await bot.send_message(
                                int(PUBLIC_CHANNEL_ID),
                                f"✅ <b>Successful Exchange!</b>\n\n"
                                f"🔄 {cur_from} ➡️ {cur_to}\n"
                                f"💰 Amount: <b>{swap['amount_from']} {cur_from}</b>\n"
                                f"⚡️ Status: #Completed"
                            )
                        except Exception as e:
                            logger.error(f"Error sending to Public Channel: {e}")

                    # 3. Уведомление ПОЛЬЗОВАТЕЛЯ в личку
                    if new_status in NOTIFY_ON:
                        message = STATUS_MESSAGES.get(new_status)
                        if new_status == "finished":
                            amount_to = result.get("amountTo") or swap.get("amount_to", "")
                            ticker_to = (result.get("tickerTo") or swap.get("currency_to", "")).split('_')[0]
                            text = (
                                f"✅ <b>Exchange completed!</b>\n\n"
                                f"ID: <code>{swap['exchange_id']}</code>\n"
                                f"Received: <b>{amount_to} {ticker_to.upper()}</b>\n\n"
                                f"Thank you for using our bot! 🙌"
                            )
                        else:
                            text = (
                                f"{message}\n\n"
                                f"ID: <code>{swap['exchange_id']}</code>"
                            )

                        await bot.send_message(chat_id=swap["user_id"], text=text)

                except Exception as e:
                    logger.error(f"Error checking swap {swap.get('exchange_id')}: {e}")

        except Exception as e:
            logger.error(f"check_swaps loop error: {e}")
