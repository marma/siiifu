FROM ubuntu:17.04

RUN apt-get update #
RUN apt-get -y install apt-utils
RUN apt-get -y install dialog
RUN apt-get -y install trafficserver

COPY records.config /etc/trafficserver/
COPY remap.config /etc/trafficserver/
COPY ssl_multicert.config /etc/trafficserver/

EXPOSE 8080
EXPOSE 8443

RUN touch /var/log/trafficserver/error.log /var/log/trafficserver/diags.log && \
    chown trafficserver:trafficserver /var/log/trafficserver/error.log /var/log/trafficserver/diags.log /etc/trafficserver/*.config

RUN openssl req -x509 -newkey rsa:4096 -keyout /etc/trafficserver/key.pem -out /etc/trafficserver/cert.pem -days 365 -subj '/CN=localhost' -nodes
CMD service trafficserver start && sleep 3 && tail -f /var/log/trafficserver/manager.log -f /var/log/trafficserver/traffic.out -f /var/log/trafficserver/error.log -f /var/log/trafficserver/diags.log
