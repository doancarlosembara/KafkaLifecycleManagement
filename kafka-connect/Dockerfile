FROM confluentinc/cp-kafka-connect:7.5.0

# Copy plugins (dari konteks build = ./kafka-connect)
COPY plugins /usr/share/confluent-hub-components

ENV CONNECT_PLUGIN_PATH="/usr/share/confluent-hub-components"
