FROM ubuntu:17.04

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

# build and install FlashPIX
RUN curl --location --remote-name http://www.imagemagick.org/download/delegates/libfpx-1.3.1-7.tar.gz && \
    tar xvfz libfpx-1.3.1-7.tar.gz && \
    cd libfpx-1.3.1-7 && \
    export CXXFLAGS=-fpermissive && \
    ./configure --prefix=/usr && \
    make && \
    make install

# build and install ImageMagick with PNG, TIFF, JPEG, JPEG 2000 and FlashPix support
RUN curl --location --remote-name https://www.imagemagick.org/download/ImageMagick-7.0.5-4.tar.gz && \
    tar xvfz ImageMagick-7.0.5-4.tar.gz && \
    cd ImageMagick-7.0.5-4 && \
    LIBOPENJP2_LIBS=/usr/lib/x86_64-linux-gnu/libopenjp2.so && \
    ./configure --prefix=/usr && \
    make && \
    make install

COPY requirements.txt /
RUN pip3 install --no-cache-dir -r /requirements.txt

EXPOSE 5000

ADD . /app
COPY bash_aliases /root/.bash_aliases
#RUN . /root/.bash_aliases
 
CMD /usr/local/bin/gunicorn --pythonpath /app -b :5000 siifu:app
