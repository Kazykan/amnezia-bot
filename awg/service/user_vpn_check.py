import json
import logging
import os
import subprocess
from service.amnezia_server import deploy_to_all_servers
from service.db_instance import user_db
from settings import WG_CONFIG_FILE, DOCKER_CONTAINER

logger = logging.getLogger(__name__)


def get_all_users_vpn():
    """Получение json пользователей которые активны или нет"""
    config_list = []
    activ_users = user_db.get_active_users()
    deactivate_users = user_db.get_users_expired_yesterday()

    for user in activ_users:
        user_config = user_db.get_config_by_telegram_id(user.telegram_id)
        config_list.append(
            {
                "client_name": str(user.telegram_id),
                "new_preshared_key": user_config.preshared_key,
            }
        )

    for user in deactivate_users:
        user_config = user_db.get_config_by_telegram_id(user.telegram_id)
        config_list.append(
            {
                "client_name": str(user.telegram_id),
                "new_preshared_key": "18Yi5MBAZPf9kX8U2wr95+fbl/fo3JxLRcsPfOVLD2M=",
            }
        )
    for entry in config_list:
        logger.info(f"Client: {entry}")
    return config_list


def update_vpn_state():
    """Обновление состояния VPN пользователей"""
    data = get_all_users_vpn()
    cmd = ["./updatepresharekey.sh", WG_CONFIG_FILE, DOCKER_CONTAINER]
    try:
        result = subprocess.run(
            cmd, input=json.dumps(data), text=True, capture_output=True, check=True
        )
        logger.info(result.stdout)

        deploy_to_all_servers()
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during VPN update: {e.stderr}")
        return False
