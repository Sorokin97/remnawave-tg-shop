import logging
from pathlib import Path
from typing import Optional, Union

from aiogram import types
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto, LinkPreviewOptions


MENU_IMAGES_ROOT = Path("/app/bot/static/images")


async def update_menu_message(
    message: Optional[types.Message],
    text: str,
    image_filename: Optional[str],
    reply_markup=None,
    parse_mode: Optional[str] = ParseMode.HTML,
    disable_link_preview: bool = True,
) -> bool:
    """Update a menu message with an image background when possible.

    Returns True if an image was used as the background, False if the text fallback
    was used or the update failed.
    """

    if not message:
        logging.error("update_menu_message called without a message instance")
        return False

    link_preview_options = None
    if disable_link_preview:
        link_preview_options = LinkPreviewOptions(is_disabled=True)

    if image_filename:
        image_path = MENU_IMAGES_ROOT / image_filename
        if image_path.is_file():
            try:
                media = InputMediaPhoto(
                    media=FSInputFile(str(image_path)),
                    caption=text,
                    parse_mode=parse_mode,
                )
                await message.edit_media(media=media, reply_markup=reply_markup)
                return True
            except TelegramBadRequest as media_error:
                logging.warning(
                    "Failed to edit media for menu using %s: %s",
                    image_path,
                    media_error,
                )
                if message.photo:
                    try:
                        await message.edit_caption(
                            caption=text,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode,
                        )
                        return True
                    except TelegramBadRequest as caption_error:
                        logging.warning(
                            "Failed to edit caption for menu image %s: %s",
                            image_path,
                            caption_error,
                        )
                    except Exception as caption_error:
                        logging.error(
                            "Unexpected error while editing caption for %s: %s",
                            image_path,
                            caption_error,
                        )
            except Exception as media_error:
                logging.error(
                    "Unexpected error while editing menu media %s: %s",
                    image_path,
                    media_error,
                )
        else:
            logging.warning("Menu image file not found: %s", image_path)

    # If we didn't render a new media and the current message already has a photo,
    # try editing the caption instead of the text to preserve the existing image.
    if message.photo:
        try:
            await message.edit_caption(
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return True
        except TelegramBadRequest as caption_error:
            if "not modified" in str(caption_error).lower():
                logging.debug(
                    "Menu caption not modified for message %s", message.message_id
                )
            else:
                logging.warning(
                    "Failed to edit existing menu caption: %s", caption_error
                )
        except Exception as caption_error:
            logging.error(
                "Unexpected error while editing existing menu caption: %s",
                caption_error,
            )

    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            link_preview_options=link_preview_options,
        )
    except TelegramBadRequest as text_error:
        if "message is not modified" in str(text_error).lower():
            logging.debug("Menu text not modified for message %s", message.message_id)
        else:
            logging.error("Failed to edit menu text: %s", text_error)
    except Exception as text_error:
        logging.error("Unexpected error while editing menu text: %s", text_error)
    return False


async def render_menu_content(
    event: Union[types.Message, types.CallbackQuery],
    text: str,
    image_filename: Optional[str] = None,
    reply_markup=None,
    parse_mode: Optional[str] = ParseMode.HTML,
    disable_link_preview: bool = True,
) -> bool:
    """
    Edit an existing menu message (preferring media where available) or send a new
    one with an optional background image.

    Returns True when a media-based message was used (photo or caption), False when
    a plain text message was sent or editing failed.
    """

    if isinstance(event, types.CallbackQuery):
        target_message = event.message
    elif isinstance(event, types.Message):
        target_message = event
    else:
        target_message = None

    if not target_message:
        logging.error("render_menu_content called without a target message")
        return False

    if isinstance(event, types.CallbackQuery):
        return await update_menu_message(
            target_message,
            text,
            image_filename,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_link_preview=disable_link_preview,
        )

    image_used = False
    image_path = None
    if image_filename:
        image_path = MENU_IMAGES_ROOT / image_filename
        if image_path.is_file():
            try:
                await target_message.bot.send_photo(
                    chat_id=target_message.chat.id,
                    photo=FSInputFile(str(image_path)),
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
                return True
            except Exception as send_photo_error:
                logging.warning(
                    "Failed to send menu photo %s: %s", image_path, send_photo_error
                )

    try:
        link_preview_options = (
            LinkPreviewOptions(is_disabled=True) if disable_link_preview else None
        )
        await target_message.bot.send_message(
            chat_id=target_message.chat.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            link_preview_options=link_preview_options,
        )
    except Exception as send_text_error:
        logging.error("Failed to send menu text: %s", send_text_error)
    return image_used
