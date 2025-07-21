import logging
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.filters import Command
from matplotlib.pylab import longlong

from keyboard.menu import get_instruction_type

router = Router()


@router.callback_query(F.data == "instruction_iphone")
async def send_iphone_instruction(callback: CallbackQuery):
    if callback.bot is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    try:
        screenshots = [
            FSInputFile("media/iphone_step1.jpg"),  # Нажать на файл 123144.conf
            FSInputFile("media/iphone_step2.jpg"),  # Нажать "Поделиться"
            FSInputFile("media/iphone_step3.jpg"),  # Нажать "Поделиться"
            FSInputFile(
                "media/iphone_step4.jpg"
            ),  # Выбрать "AmneziaWG" → Нажать "Подключить"
        ]

        captions = [
            "📱 *Шаг 1:* Нажмите на файл `.conf`, который вы получили.",
            "📤 *Шаг 2:* Нажмите кнопку *«Поделиться»*",
            "📤 *Шаг 3:* Нажмите кнопку *«Поделиться»*, затем — *«Ещё» (три точки)*.",
            "🅦 *Шаг 4:* Выберите *AmneziaWG* из списка приложений и нажмите *«Подключить»*.",
        ]

        for i in range(len(screenshots)):
            if isinstance(callback.message, Message):
                await callback.message.answer_photo(
                    photo=screenshots[i], caption=captions[i], parse_mode="Markdown"
                )
            else:
                await callback.bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=screenshots[i],
                    caption=captions[i],
                    parse_mode="Markdown",
                )

    except Exception as e:
        await callback.answer(
            "⚠ Произошла ошибка при отправке инструкции. Попробуйте позже."
        )
        import logging

        logging.exception("Ошибка при отправке инструкции")


@router.callback_query(F.data == "instruction_android")
async def send_android_instruction(callback: CallbackQuery):
    if callback.bot is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    try:
        screenshots = [
            FSInputFile("media/android_step1.jpg"),  # Нажать на файл 123144.conf
            FSInputFile("media/android_step2.jpg"),  # Выбрать "AmneziaWG"
            FSInputFile("media/android_step3.jpg"),  # Нажать "Подключить"
        ]

        captions = [
            "📱 *Шаг 1:* Нажмите на файл `.conf`, который вы получили.",
            "🅦 *Шаг 4:* Выберите *AmneziaVPN* из списка приложений",
            "🌐 нажмите *«Подключиться»*.",
        ]

        for i in range(len(screenshots)):
            if isinstance(callback.message, Message):
                await callback.message.answer_photo(
                    photo=screenshots[i], caption=captions[i], parse_mode="Markdown"
                )
            else:
                await callback.bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=screenshots[i],
                    caption=captions[i],
                    parse_mode="Markdown",
                )

    except Exception as e:
        await callback.answer(
            "⚠ Произошла ошибка при отправке инструкции. Попробуйте позже."
        )
        import logging

        logging.exception("Ошибка при отправке инструкции")


@router.callback_query(F.data == "instructions")
async def show_instructions(callback: CallbackQuery):

    text = (
        "Чтобы начать, сначала скачайте приложение, затем установите его. После установки выберите тип вашего устройства, чтобы получить подробные инструкции.\n\n"
        "Ссылки для скачивания AmneziaVPN:\n"
        "📱 Если у вас iPhone или iPad – скачайте приложение здесь: [App Store](https://apps.apple.com/ru/app/amneziawg/id6478942365)\n\n"
        "🤖 Если у вас Android – скачайте приложение здесь: [Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n\n"
        "После установки выберите свое устройство, чтобы узнать, как настроить приложение."
    )

    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                text=text,
                disable_web_page_preview=True,
                reply_markup=get_instruction_type(),
            )
        except Exception as e:
            logging.info(f"Ошибка при редактировании сообщения с инструкциями\n{e}")
            await callback.message.answer(
                text=text,
                disable_web_page_preview=True,
                reply_markup=get_instruction_type(),
            )
    await callback.answer()
