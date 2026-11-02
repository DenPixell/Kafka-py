#!/bin/sh
# Создаёт по базе и пользователю на каждый сервис.
# Сервис владеет только своей базой: в чужую он не зайдёт даже по ошибке.
# Скрипт выполняется один раз, при первом создании тома с данными.
set -eu

create_db() {
    db="$1"
    user="$2"
    password="$3"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE USER $user WITH PASSWORD '$password';
CREATE DATABASE $db OWNER $user;
REVOKE CONNECT ON DATABASE $db FROM PUBLIC;
SQL
}

create_db orders "$ORDER_DB_USER" "$ORDER_DB_PASSWORD"
create_db inventory "$INVENTORY_DB_USER" "$INVENTORY_DB_PASSWORD"
create_db antifraud "$ANTIFRAUD_DB_USER" "$ANTIFRAUD_DB_PASSWORD"
