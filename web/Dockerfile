FROM ubuntu:17.10

RUN apt-get update && \
    apt-get install -y gcc && \
    apt-get install -y pkg-config && \
    apt-get install -y curl && \
    apt-get install -y python3 && \
    apt-get install -y python3-pip && \
    apt-get install -y libjpeg-dev && \
    apt-get install -y libpng-dev && \
    apt-get install -y libopenjp2-7 && \
    apt-get install -y libopenjp2-7-dev && \
    apt-get install -y libopenjp2-tools

ENV LANG=C.UTF-8

ADD . /app
RUN pip3 install --no-cache-dir -r /app/requirements.txt
EXPOSE 5000
 
CMD /usr/local/bin/gunicorn --pythonpath /app -b :5000 siiifu:app
