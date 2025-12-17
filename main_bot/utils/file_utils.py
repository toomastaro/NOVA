"""
Утилиты для работы с файлами (изображения, видео).

Этот модуль содержит функции для:
- Обработки изображений для сторис (изменение размера, добавление фона)
- Обработки видео для сторис (изменение размера, добавление размытого фона)
- Определения цветов и режимов изображений

Все тяжелые операции выполняются в отдельном потоке (executor), чтобы не блокировать event loop.
"""

import asyncio
import logging
import math
import os
import pathlib
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, Union

import ffmpeg
from PIL import Image

logger = logging.getLogger(__name__)

# Определяем пути
CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
TEMP_DIR = CURRENT_DIR / "temp"

# Создаем папку для временных файлов, если её нет
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Пул потоков для тяжелых операций
_executor = ThreadPoolExecutor(max_workers=4)


def get_mode(image: Image.Image) -> str:
    """
    Получает корректный режим изображения.

    Аргументы:
        image (Image.Image): Объект PIL Image.

    Возвращает:
        str: Режим изображения ('RGB' или 'RGBA').
    """
    if image.mode not in ["RGB", "RGBA"]:
        return "RGB"
    return image.mode


def get_color(image: Image.Image) -> Tuple[int, int, int, int]:
    """
    Вычисляет средний цвет изображения с учетом альфа-канала.

    Использует квадратичное усреднение для более точного результата.

    Аргументы:
        image (Image.Image): Объект PIL Image.

    Возвращает:
        Tuple[int, int, int, int]: Средние значения цветов (red, green, blue, alpha).
    """
    mode = get_mode(image)
    if mode != image.mode:
        image = image.convert("RGB")

    red_total = 0
    green_total = 0
    blue_total = 0
    alpha_total = 0
    count = 0

    pixel = image.load()
    if not pixel:
        return (0, 0, 0, 0)

    for i in range(image.width):
        for j in range(image.height):
            color = pixel[i, j]
            if len(color) == 4:
                red, green, blue, alpha = color
            else:
                [red, green, blue], alpha = color, 255

            red_total += red * red * alpha
            green_total += green * green * alpha
            blue_total += blue * blue * alpha
            alpha_total += alpha

            count += 1

    if count == 0:
        return (0, 0, 0, 0)

    return (
        round(math.sqrt(red_total / alpha_total)),
        round(math.sqrt(green_total / alpha_total)),
        round(math.sqrt(blue_total / alpha_total)),
        round(alpha_total / count),
    )


def _process_image_sync(photo: Union[str, pathlib.Path], chat_id: int) -> str:
    """
    Синхронная версия обработки фото.

    Аргументы:
        photo (Union[str, pathlib.Path]): Путь к файлу.
        chat_id (int): ID чата.

    Возвращает:
        str: Путь к обработанному файлу.
    """
    try:
        # Если photo - это путь к файлу, убедимся что это строка или Path
        with Image.open(photo) as img:
            mask = Image.new("RGBA", (540, 960), get_color(img))

            if img.width < 540:
                img = img.resize((540, 960))
                img.thumbnail((540, 960))

            if img.width > 540:
                img.thumbnail((540, 960))

            height = int(960 / 2 - img.height / 2)

            mask.paste(img, (0, height), img.convert("RGBA"))

            # Сохраняем во временную директорию
            # Используем str(TEMP_DIR) для совместимости с save
            output_filename = f"{chat_id}.png"
            output_path = TEMP_DIR / output_filename
            mask.save(str(output_path))

            return str(output_path)
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}", exc_info=True)
        raise e


async def get_path(photo: Union[str, pathlib.Path], chat_id: int) -> str:
    """
    Асинхронная обертка для обработки фото.
    Запускает обработку в executor'е.

    Аргументы:
        photo (Union[str, pathlib.Path]): Путь к файлу или file-like объект с изображением.
        chat_id (int): ID чата для формирования имени файла.

    Возвращает:
        str: Путь к обработанному файлу.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _process_image_sync, photo, chat_id)


def _process_video_sync(
    input_path: Union[str, pathlib.Path], chat_id: int
) -> Optional[str]:
    """
    Синхронная версия обработки видео.

    Аргументы:
        input_path (Union[str, pathlib.Path]): Путь к исходному видео.
        chat_id (int): ID чата.

    Возвращает:
        Optional[str]: Путь к обработанному видео или None.
    """
    # Гарантируем строковый путь
    input_path = str(input_path)
    base_name = f"{abs(chat_id)}"

    # Получаем расширение безопасно
    _, extension = os.path.splitext(input_path)
    if not extension:
        extension = ".mp4"  # Fallback
    # Убираем точку если она есть (для ffmpeg путей может быть важно, но здесь splitext оставляет точку)
    # В оригинале было split('.')[1], что ненадежно

    # Формируем пути
    tmp_path = TEMP_DIR / f"{base_name}_tmp{extension}"
    output_path = TEMP_DIR / f"{base_name}_final{extension}"

    tmp_path_str = str(tmp_path)
    output_path_str = str(output_path)

    try:
        probe = ffmpeg.probe(input_path)
        stream = next((s for s in probe["streams"] if s.get("width")), None)
        if not stream:
            raise RuntimeError("Не удалось определить разрешение видео")

        width, height = stream["width"], stream["height"]

        # Для горизонтальных видео добавляем размытый фон
        if width >= height:
            (
                ffmpeg.input(input_path)
                .filter("scale", "iw", "2*trunc(iw*16/18)")
                .filter(
                    "boxblur",
                    "luma_radius=min(h\\,w)/5",
                    "luma_power=1",
                    "chroma_radius=min(cw\\,ch)/5",
                    "chroma_power=1",
                )
                .overlay(ffmpeg.input(input_path), x="(W-w)/2", y="(H-h)/2")
                .filter("setsar", 1)
                .output(
                    tmp_path_str, loglevel="error", y=None
                )  # Changed loglevel to error to reduce noise
                .run()
            )
            intermediate_file = tmp_path_str
        else:
            # Для вертикальных видео используем исходное
            intermediate_file = input_path

        # Финальное изменение размера до 540x960
        (
            ffmpeg.input(intermediate_file)
            .filter("scale", 540, 960)
            .output(output_path_str, loglevel="error", y=None)
            .run()
        )

        return output_path_str

    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}", exc_info=True)
        return None
    finally:
        # Очистка временных файлов (кроме финального и исходного)
        if (
            "tmp_path_str" in locals()
            and os.path.exists(tmp_path_str)
            and tmp_path_str != output_path_str
        ):
            try:
                os.remove(tmp_path_str)
            except Exception as ex:
                logger.warning(
                    f"Не удалось удалить временный файл {tmp_path_str}: {ex}"
                )


async def get_path_video(
    input_path: Union[str, pathlib.Path], chat_id: int
) -> Optional[str]:
    """
    Асинхронная обертка для обработки видео.
    Запускает ffmpeg в executor'е.

    Аргументы:
        input_path (Union[str, pathlib.Path]): Путь к исходному видео.
        chat_id (int): ID чата для формирования имени файла.

    Возвращает:
        Optional[str]: Путь к обработанному видео или None при ошибке.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _executor, _process_video_sync, input_path, chat_id
    )
