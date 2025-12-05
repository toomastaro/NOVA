"""
Утилиты для работы с файлами (изображения, видео).

Этот модуль содержит функции для:
- Обработки изображений для сторис (изменение размера, добавление фона)
- Обработки видео для сторис (изменение размера, добавление размытого фона)
- Определения цветов и режимов изображений
"""
import math
import os
import logging

import ffmpeg
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)


def get_mode(image: Image) -> str:
    """
    Получить корректный режим изображения.
    
    Args:
        image: Объект PIL Image
        
    Returns:
        Режим изображения ('RGB' или 'RGBA')
    """
    if image.mode not in ['RGB', 'RGBA']:
        return 'RGB'
    return image.mode


def get_color(image: Image):
    """
    Вычислить средний цвет изображения с учетом альфа-канала.
    
    Использует квадратичное усреднение для более точного результата.
    
    Args:
        image: Объект PIL Image
        
    Returns:
        Tuple (red, green, blue, alpha) - средние значения цветов
    """
    mode = get_mode(image)
    if mode != image.mode:
        image = image.convert('RGB')

    red_total = 0
    green_total = 0
    blue_total = 0
    alpha_total = 0
    count = 0

    pixel = image.load()

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

    return (
        round(math.sqrt(red_total / alpha_total)),
        round(math.sqrt(green_total / alpha_total)),
        round(math.sqrt(blue_total / alpha_total)),
        round(alpha_total / count)
    )


def get_path(photo, chat_id):
    """
    Обработать фото для сторис (540x960).
    
    Изменяет размер изображения, добавляет фон среднего цвета,
    центрирует изображение.
    
    Args:
        photo: Путь к файлу или file-like объект с изображением
        chat_id: ID чата для формирования имени файла
        
    Returns:
        Путь к обработанному файлу
    """
    with Image.open(photo) as img:

        mask = Image.new("RGBA", (540, 960), get_color(img))

        if img.width < 540:
            img = img.resize((540, 960))
            img.thumbnail((540, 960))

        if img.width > 540:
            img.thumbnail((540, 960))

        height = int(960 / 2 - img.height / 2)

        mask.paste(
            img,
            (0, height),
            img.convert('RGBA')
        )

        path = str(chat_id) + '.png'
        mask.save(path)

        return path


def get_path_video(input_path: str, chat_id: int):
    """
    Обработать видео для сторис (540x960).
    
    Для горизонтальных видео добавляет размытый фон,
    для вертикальных просто изменяет размер.
    
    Args:
        input_path: Путь к исходному видео
        chat_id: ID чата для формирования имени файла
        
    Returns:
        Путь к обработанному видео или None при ошибке
    """
    base_name = f"{abs(chat_id)}"
    extension = input_path.split('.')[1]
    tmp_path = f"main_bot/utils/temp/{base_name}_tmp.{extension}"
    output_path = f"main_bot/utils/temp/{base_name}_final.{extension}"

    try:
        probe = ffmpeg.probe(input_path)
        stream = next((s for s in probe["streams"] if s.get("width")), None)
        if not stream:
            raise RuntimeError("Не удалось определить разрешение видео")

        width, height = stream["width"], stream["height"]
        
        # Для горизонтальных видео добавляем размытый фон
        if width >= height:
            (
                ffmpeg
                .input(input_path)
                .filter("scale", "iw", "2*trunc(iw*16/18)")
                .filter(
                    "boxblur",
                    "luma_radius=min(h\\,w)/5",
                    "luma_power=1",
                    "chroma_radius=min(cw\\,ch)/5",
                    "chroma_power=1"
                )
                .overlay(ffmpeg.input(input_path), x="(W-w)/2", y="(H-h)/2")
                .filter("setsar", 1)
                .output(tmp_path, loglevel="quiet", y=None)
                .run()
            )
        else:
            # Для вертикальных видео используем исходное
            tmp_path = input_path

        # Финальное изменение размера до 540x960
        (
            ffmpeg
            .input(tmp_path)
            .filter("scale", 540, 960)
            .output(output_path, loglevel="quiet", y=None)
            .run()
        )

        return output_path

    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}")
        return None
    finally:
        # Очистка временных файлов
        for f in (input_path, tmp_path):
            if os.path.exists(f) and f != output_path:
                try:
                    os.remove(f)
                except Exception as ex:
                    logger.warning(f"Не удалось удалить {f}: {ex}")
