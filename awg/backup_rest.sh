#!/bin/bash
set -e

# --- Configuration ---
LOCAL_FILES_DIR="files" # Локальная папка на хосте, содержащая server.conf и clientsTable
CONTAINER_CLIENTS_TABLE_PATH="/opt/amnezia/awg/clientsTable" # Путь к файлу clientsTable внутри контейнера (фиксирован из ваших скриптов)

if [ "$#" -lt 2 ]; then
    echo "Использование: $0 <путь_wg_конфигурации_внутри_контейнера> <имя_или_ID_docker_контейнера>"
    echo "Пример: $0 /opt/amnezia/awg/wg0.conf amnezia-wg"
    echo "Ошибкa: Недостаточно аргументов. Требуется путь к конфигу WG и имя контейнера."
    exit 1
fi

# Назначаем переменные согласно вашему запросу, используя позиционные параметры этого скрипта ($1 и $2)
WG_CONFIG_FILE="$1"     # Путь к файлу конфигурации WG внутри контейнера (первый аргумент этому скрипту)
DOCKER_CONTAINER="$2"   # Имя или ID Docker контейнера (второй аргумент этому скрипту)


# --- Локальные пути к файлам ---
LOCAL_SERVER_CONF="$LOCAL_FILES_DIR/server.conf"
LOCAL_CLIENTS_TABLE="$LOCAL_FILES_DIR/clientsTable"

# --- Предварительные проверки ---
echo "Проверка наличия локальных файлов..."
if [ ! -f "$LOCAL_SERVER_CONF" ]; then
    echo "Ошибка: Локальный файл не найден: $LOCAL_SERVER_CONF"
    exit 1
fi
echo "Файл $LOCAL_SERVER_CONF найден."

if [ ! -f "$LOCAL_CLIENTS_TABLE" ]; then
    echo "Ошибка: Локальный файл не найден: $LOCAL_CLIENTS_TABLE"
    exit 1
fi
echo "Файл $LOCAL_CLIENTS_TABLE найден."

echo "\nПроверка Docker контейнера '$DOCKER_CONTAINER'..."
# Проверяем, существует ли контейнер и запущен ли он
if ! docker inspect -f '{{.State.Running}}' "$DOCKER_CONTAINER" &> /dev/null; then
    echo "Ошибка: Docker контейнер '$DOCKER_CONTAINER' не найден или не запущен."
    exit 1
fi
echo "Контейнер '$DOCKER_CONTAINER' найден и запущен."

# --- Подтверждение ---
echo "\nВнимание: Этот скрипт заменит следующие файлы внутри контейнера '$DOCKER_CONTAINER':"
echo "  - ${WG_CONFIG_FILE}"
echo "  - ${CONTAINER_CLIENTS_TABLE_PATH}"
echo "локальными файлами из директории '${LOCAL_FILES_DIR}/'."
echo "Убедитесь, что вы запускаете этот скрипт из директории, содержащей папку '${LOCAL_FILES_DIR}/'."

read -p "Вы уверены, что хотите продолжить? (y/n): " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Операция отменена.\n"
    exit 0
fi

# --- Копирование файлов ---
echo "\nКопируем файлы в контейнер '$DOCKER_CONTAINER'..."

# Копируем server.conf в путь, указанный в WG_CONFIG_FILE
echo "Копирование $LOCAL_SERVER_CONF в $DOCKER_CONTAINER:${WG_CONFIG_FILE}..."
if docker cp "$LOCAL_SERVER_CONF" "$DOCKER_CONTAINER:${WG_CONFIG_FILE}"; then
    echo "Успешно скопирован $LOCAL_SERVER_CONF."
else
    echo "Ошибка при копировании $LOCAL_SERVER_CONF. Отмена."
    exit 1
fi

# Копируем clientsTable в фиксированный путь внутри контейнера
echo "Копирование $LOCAL_CLIENTS_TABLE в $DOCKER_CONTAINER:${CONTAINER_CLIENTS_TABLE_PATH}..."
if docker cp "$LOCAL_CLIENTS_TABLE" "$DOCKER_CONTAINER:${CONTAINER_CLIENTS_TABLE_PATH}"; then
    echo "Успешно скопирован $LOCAL_CLIENTS_TABLE."
else
    echo "Ошибка при копировании $LOCAL_CLIENTS_TABLE. Отмена."
    exit 1
fi

# --- Применяем изменения (перезагружаем WireGuard) ---
echo "\nПытаемся перезагрузить конфигурацию WireGuard внутри контейнера..."
# Эта команда перезагружает конфигурацию WG. Возможно, потребуется изменить, если ваш контейнер использует другой метод.
# Используем 'sh -c' для выполнения нескольких команд и обработки путей с пробелами
if docker exec "$DOCKER_CONTAINER" sh -c "wg-quick down \"${WG_CONFIG_FILE}\" && wg-quick up \"${WG_CONFIG_FILE}\""; then
     echo "Конфигурация WireGuard успешно перезагружена."
else
     echo "Внимание: Не удалось перезагрузить конфигурацию WireGuard внутри контейнера."
     echo "Возможно, потребуется вручную перезапустить контейнер или сервис для применения изменений."
     echo "Команда, которая не выполнилась: docker exec \"$DOCKER_CONTAINER\" sh -c \"wg-quick down \\\"${WG_CONFIG_FILE}\\\" && wg-quick up \\\"${WG_CONFIG_FILE}\\\"\""
fi


echo "\nПроцесс замены файлов завершен.\n"
exit 0