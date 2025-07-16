import subprocess
import tempfile
import os
import io
import re
import pandas as pd
from datetime import datetime
import subprocess
import seaborn as sns
import matplotlib.pyplot as plt


# Функция для получения данных vnstat
def get_vnstat_hourly():
    result = subprocess.run(["vnstat", "-h"], capture_output=True, text=True)
    return result.stdout


# Функция поиска максимальной нагрузки по total и avg. rate
def find_peak_usage(vnstat_data):
    lines = vnstat_data.split("\n")
    peak_hour_total = None
    peak_hour_avg = None
    peak_total = 0.0
    peak_avg_rate = 0.0

    for line in lines:
        parts = line.split()
        if len(parts) >= 10:  # Проверяем, достаточно ли элементов
            try:
                time = parts[0]  # Время
                total = float(parts[4])  # Total (MiB/GiB)
                avg_rate = float(parts[7])  # Avg. rate (kbit/s или Mbit/s)

                # Конвертация в единицы измерения
                if "MiB" in parts[7]:
                    total /= 1024  # MiB → GiB
                if "kbit/s" in parts[9]:
                    avg_rate /= 1024  # kbit/s → Mbit/s

                if total > peak_total:
                    peak_total = total
                    peak_hour_total = time

                if avg_rate > peak_avg_rate:
                    peak_avg_rate = avg_rate
                    peak_hour_avg = time

            except ValueError as e:
                print(f"eror {e}")
                continue

    return peak_hour_total, peak_total, peak_hour_avg, peak_avg_rate


def convert_to_mib(value, unit):
    if unit == "GiB":
        return value * 1024
    elif unit == "MiB":
        return value
    elif unit == "KiB":
        return value / 1024
    return 0.0


def convert_to_mbit(value, unit):
    if unit == "kbit/s":
        return value / 1000
    elif unit == "Mbit/s":
        return value
    elif unit == "Gbit/s":
        return value * 1000
    return 0.0


def parse_vnstat_hourly():
    lines = get_vnstat_hourly()
    data = []
    current_date = None

    for line in lines.splitlines():
        line = line.strip()

        # Пропускаем заголовки и разделители
        if re.match(r"^-+$", line.replace("+", "").replace("|", "").replace(" ", "")):
            continue
        if not line:
            continue

        # Если строка с датой
        if re.match(r"^\d{4}-\d{2}-\d{2}$", line.strip()):
            current_date = line.strip()
            continue

        # Обрабатываем строки с данными
        if current_date:
            parts = line.split("|")
            if len(parts) != 4:
                continue  # некорректная строка

            try:
                hour = parts[0].strip().split()[0]
                total_str = parts[2].strip()
                avg_str = parts[3].strip()

                # Извлекаем total
                total_match = re.match(r"([\d.]+)\s*(MiB|GiB|KiB)", total_str)
                total_value = float(total_match.group(1))
                total_unit = total_match.group(2)

                # Извлекаем avg rate
                avg_match = re.match(r"([\d.]+)\s*(kbit/s|Mbit/s|Gbit/s)", avg_str)
                avg_value = float(avg_match.group(1))
                avg_unit = avg_match.group(2)

                dt = datetime.strptime(f"{current_date} {hour}", "%Y-%m-%d %H:%M")
                total_mib = convert_to_mib(total_value, total_unit)
                avg_rate_mbit = convert_to_mbit(avg_value, avg_unit)

                data.append(
                    {"datetime": dt, "total": total_mib, "avg_rate": avg_rate_mbit}
                )
            except Exception as e:
                print(f"Ошибка при обработке строки: {line}\n{e}")

    return data


# def plot_traffic_to_buffer(data):

#     df = pd.DataFrame(data)

#     plt.figure(figsize=(12, 6))
#     sns.lineplot(data=df, x="datetime", y="total", label="Total (MiB)")
#     sns.lineplot(data=df, x="datetime", y="avg_rate", label="Avg. Rate (Mbit/s)")
#     plt.xticks(rotation=45)
#     plt.ylabel("Usage")
#     plt.title("Hourly Network Traffic (vnstat)")
#     plt.tight_layout()

#     buf = io.BytesIO()
#     plt.savefig(buf, format="png")
#     buf.seek(0)
#     plt.close()
#     return buf

def get_vnstati_image_to_buffer(header_text="local"):
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            temp_path = tmp_file.name

        # Команда генерации изображения
        command = [
            "vnstati",
            "-s", "-hg",
            "--headertext", header_text,
            "-o", temp_path
        ]
        subprocess.run(command, check=True)

        # Чтение изображения в буфер
        with open(temp_path, "rb") as f:
            image_bytes = f.read()

        buffer = io.BytesIO(image_bytes)
        buffer.seek(0)

        # Удаление временного файла
        os.remove(temp_path)

        return buffer

    except subprocess.CalledProcessError as e:
        print(f"Ошибка при запуске vnstati: {e}")
        return None
    except Exception as e:
        print(f"Не удалось получить изображение: {e}")
        return None
