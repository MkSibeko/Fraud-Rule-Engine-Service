# Start everything
docker compose up --build

# Consume messages from host
docker exec broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:29092 \
  --topic transactions --from-beginning

# Scale up transactions without rebuilding
docker compose run --rm -e NUM_TRANSACTIONS=500 producer