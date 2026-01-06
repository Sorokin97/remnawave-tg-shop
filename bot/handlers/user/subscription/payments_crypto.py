from typing import Optional

from aiogram import F, Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.user_keyboards import get_payment_url_keyboard
from bot.middlewares.i18n import JsonI18n
from bot.services.crypto_pay_service import CryptoPayService
from config.settings import Settings
from bot.handlers.user.subscription.core import _menu_image_if_exists, _send_menu_with_image, render_subscribe_menu

router = Router(name="user_subscription_payments_crypto_router")


@router.callback_query(F.data.startswith("pay_crypto:"))
async def pay_crypto_callback_handler(
    callback: types.CallbackQuery,
    settings: Settings,
    i18n_data: dict,
    session: AsyncSession,
    cryptopay_service: CryptoPayService,
):
    current_lang = i18n_data.get("current_language", settings.DEFAULT_LANGUAGE)
    i18n: Optional[JsonI18n] = i18n_data.get("i18n_instance")
    get_text = (lambda key, **kwargs: i18n.gettext(current_lang, key, **kwargs) if i18n else key)

    if not i18n or not callback.message:
        try:
            await callback.answer(get_text("error_occurred_try_again"), show_alert=True)
        except Exception:
            pass
        return

    if not cryptopay_service or not getattr(cryptopay_service, "configured", False):
        try:
            await callback.answer(get_text("payment_service_unavailable_alert"), show_alert=True)
        except Exception:
            pass
        return

    try:
        _, data_payload = callback.data.split(":", 1)
        parts = data_payload.split(":")
        months = float(parts[0])
        price_amount = float(parts[1])
        sale_mode = parts[2] if len(parts) > 2 else "subscription"
    except (ValueError, IndexError):
        try:
            await callback.answer(get_text("error_try_again"), show_alert=True)
        except Exception:
            pass
        return

    user_id = callback.from_user.id
    human_value = str(int(months)) if float(months).is_integer() else f"{months:g}"
    payment_description = (
        get_text("payment_description_traffic", traffic_gb=human_value)
        if sale_mode == "traffic"
        else get_text("payment_description_subscription", months=int(months))
    )
    price_display = human_value if sale_mode == "traffic" else str(price_amount)
    currency_symbol = settings.DEFAULT_CURRENCY_SYMBOL

    invoice_url = await cryptopay_service.create_invoice(
        session=session,
        user_id=user_id,
        months=months,
        amount=price_amount,
        description=payment_description,
        sale_mode=sale_mode,
    )

    if invoice_url:
        payment_text = get_text(
            key="payment_link_message_traffic" if sale_mode == "traffic" else "payment_link_message",
            months=int(months),
            traffic_gb=human_value,
            price=price_display,
            currency_symbol=currency_symbol,
        )
        try:
            await render_subscribe_menu(
                callback.message,
                payment_text,
                reply_markup=get_payment_url_keyboard(
                    invoice_url,
                    current_lang,
                    i18n,
                    back_callback=f"subscribe_period:{human_value}",
                    back_text_key="back_to_payment_methods_button",
                ),
            )
        except Exception:
            try:
                await _send_menu_with_image(
                    callback.message,
                    payment_text,
                    _menu_image_if_exists("menu_subscribe.png"),
                    reply_markup=get_payment_url_keyboard(
                        invoice_url,
                        current_lang,
                        i18n,
                        back_callback=f"subscribe_period:{human_value}",
                        back_text_key="back_to_payment_methods_button",
                    ),
                )
            except Exception:
                pass
        try:
            await callback.answer()
        except Exception:
            pass
        return

    try:
        await callback.answer(get_text("error_payment_gateway"), show_alert=True)
    except Exception:
        pass
