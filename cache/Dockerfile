FROM ubuntu:17.04

RUN apt-get update && \
    apt-get install -y python3 && \
    apt-get install -y python3-pip

ENV LANG=C.UTF-8

COPY requirements.txt /
RUN pip3 install --no-cache-dir -r /requirements.txt

EXPOSE 5000

VOLUME /data

ADD . /app
 
CMD /usr/local/bin/gunicorn --pythonpath /app -b :5000 cache:app
