FROM ubuntu:16.04

#ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends apt-utils

RUN apt-get -y install --no-install-recommends atop zip psmisc imagemagick iproute2\ 
 && apt-get -y install --no-install-recommends iputils-ping iptables \
 && apt-get -y install --no-install-recommends mc vim\
 && apt-get -y install --no-install-recommends net-tools less python-virtualenv python-pip python-dev build-essential default-jdk git\
 && apt-get -y install --no-install-recommends libssl-dev libxml2-dev libxslt-dev python-dev lib32z1-dev libjpeg-dev\
 && apt-get clean

# ADD ./python.src /home/python.src
COPY ./docker_home/* /home/

# RUN /home/build_env.sh

ENTRYPOINT  cd /home && /bin/bash
