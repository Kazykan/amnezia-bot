#!/bin/bash

set -e

# Проверка аргументов
if [ -z "$1" ]; then
    echo "Error: CLIENT_NAME argument is not provided"
    exit 1
fi

if [ -z "$2" ]; then
    echo "Error: WG_CONFIG_FILE argument is not provided"
    exit 1
fi

if [ -z "$3" ]; then
    echo "Error: DOCKER_CONTAINER argument is not provided"
    exit 1
fi

CLIENT_NAME="$1"
WG_CONFIG_FILE="$2"
DOCKER_CONTAINER="$3"

# Валидация имени клиента
if [[ ! "$CLIENT_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Invalid CLIENT_NAME. Only letters, numbers, underscores, and hyphens are allowed."
    exit 1
fi

# Временный файл
SERVER_CONF_PATH="/tmp/wg_temp.conf"
trap 'rm -f "$SERVER_CONF_PATH"' EXIT

# Получаем конфигурацию из контейнера
docker exec -i "$DOCKER_CONTAINER" cat "$WG_CONFIG_FILE" > "$SERVER_CONF_PATH"

# Поиск нужного [Peer] блока
PEER_LINES=$(grep -n "^\[Peer\]" "$SERVER_CONF_PATH" | cut -d: -f1)

FOUND_BLOCK_START=""
FOUND_BLOCK_END=""

LINES=($(echo "$PEER_LINES"))
for i in "${!LINES[@]}"; do
    START=${LINES[$i]}
    END=${LINES[$((i+1))]:-$(wc -l < "$SERVER_CONF_PATH")}
    
    # Проверяем наличие комментария с именем клиента
    if sed -n "${START},${END}p" "$SERVER_CONF_PATH" | grep -q "# $CLIENT_NAME"; then
        FOUND_BLOCK_START=$START
        FOUND_BLOCK_END=$END
        break
    fi
done

if [ -z "$FOUND_BLOCK_START" ]; then
    echo "Error: Client $CLIENT_NAME not found in any [Peer] block"
    exit 1
fi

# Извлекаем текущий PresharedKey из найденного блока
CURRENT_PRESHARED_KEY=$(sed -n "${FOUND_BLOCK_START},${FOUND_BLOCK_END}p" "$SERVER_CONF_PATH" | grep -E "^PresharedKey\s*=" | awk -F'= ' '{print $2}')

if [ -z "$CURRENT_PRESHARED_KEY" ]; then
    echo "Error: PresharedKey not found in client block"
    exit 1
fi

# Выводим ключ
echo "$CURRENT_PRESHARED_KEY"
