import json
from scp import SCPClient  # type: ignore
import os
import paramiko
import logging

logger = logging.getLogger(__name__)


def deploy_to_all_servers(config_path="files/servers.json") -> str:
    text = "🔄 Начинаю деплой на все сервера из конфигурации..."
    with open(config_path, "r") as f:
        servers = json.load(f)

    for server in servers:
        text += f"\n- {server['ssh_host']}"
        logger.info(f"Deploying to {server['ssh_host']}...")
        deploy_and_exec(server)
        text += f"\n✅ Деплой на {server['ssh_host']} завершен."
        logger.info(f"Deployment to {server['ssh_host']} completed.")

    return text + "\n✅ Деплой на все сервера завершен."


def deploy_and_exec(server_config):
    """Загружает конфигурацию сервера и выполняет деплой."""
    ssh_host = server_config["ssh_host"]
    ssh_port = server_config["ssh_port"]
    ssh_user = server_config["ssh_user"]
    ssh_key_path = os.path.expanduser(server_config["ssh_key_path"])
    local_wg0 = server_config["local_wg0"]
    local_clients_table = server_config["local_clientsTable"]
    remote_tmp_dir = server_config["remote_tmp_dir"]
    docker_container = server_config["docker_container"]
    remote_docker_path = server_config["remote_docker_path"]

    wg_config_file = os.path.join(remote_docker_path, "wg0.conf")

    # Устанавливаем SSH-соединение
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=ssh_host, port=ssh_port, username=ssh_user, key_filename=ssh_key_path
    )

    # Создаём временную директорию на сервере
    ssh.exec_command(f"mkdir -p {remote_tmp_dir}")

    # Копируем файлы во временную директорию на сервере
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(local_wg0, remote_path=os.path.join(remote_tmp_dir, "wg0.conf"))
        scp.put(
            local_clients_table,
            remote_path=os.path.join(remote_tmp_dir, "ClientsTable"),
        )

    # Копируем файлы из временной директории в Docker-контейнер
    file_mappings = {
        "wg0.conf": os.path.join(remote_docker_path, "wg0.conf"),
        "ClientsTable": os.path.join(remote_docker_path, "ClientsTable"),
    }

    for filename, container_path in file_mappings.items():
        remote_file_path = os.path.join(remote_tmp_dir, filename)
        cmd_copy = f"docker cp {remote_file_path} {docker_container}:{container_path}"
        ssh.exec_command(cmd_copy)

    # Перезапуск WireGuard внутри контейнера
    cmd_restart = f'docker restart {docker_container}'
    ssh.exec_command(cmd_restart)

    # Закрываем SSH-соединение
    ssh.close()


def check_docker_ps(servers_json_path: str) -> str:
    with open(servers_json_path, "r") as f:
        servers = json.load(f)

    for server in servers:
        logger.info(f"\n🔄 Проверка сервера: {server['ssh_host']}")
        try:
            ssh_key_path = os.path.expanduser(server["ssh_key_path"])

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=server["ssh_host"],
                port=server.get("ssh_port", 22),
                username=server["ssh_user"],
                key_filename=ssh_key_path,
            )

            stdin, stdout, stderr = ssh.exec_command("docker ps")
            output = stdout.read().decode()
            errors = stderr.read().decode()

            if output:
                logger.info(f"✅ Результат:\n{output}")
            if errors:
                logger.warning(f"⚠️ Ошибки:\n{errors}")

            ssh.close()
            return output
        except Exception as e:
            logger.error(f"❌ Ошибка при подключении к {server['ssh_host']}: {e}")
            return f"❌ Ошибка при подключении к {server['ssh_host']}: {e}"

    logger.error("❌ Не удалось подключиться ни к одному серверу.")
    return "❌ Не удалось подключиться ни к одному серверу."
