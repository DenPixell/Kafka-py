#!/bin/sh
# Создаёт топики явно. Автосоздание в брокере выключено: опечатка в имени
# топика должна давать ошибку, а не тихо создавать новый пустой топик.
set -eu

BOOTSTRAP="kafka:29092"
PARTITIONS=3

for topic in \
    inventory.commands inventory.events \
    antifraud.commands antifraud.events \
    inventory.commands.dlq inventory.events.dlq \
    antifraud.commands.dlq antifraud.events.dlq
do
    /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" \
        --create --if-not-exists --topic "$topic" \
        --partitions "$PARTITIONS" --replication-factor 1
done

/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list
