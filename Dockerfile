##
# Create base image for prod and dev
##
FROM python:3.6 as base

ENV PYTHONUNBUFFERED 1

RUN apt-get -y update
RUN apt-get -y install libldap2-dev libsasl2-dev curl gnupg

RUN curl -sL https://deb.nodesource.com/setup_11.x | bash -
RUN apt-get -y install nodejs

COPY requirements ./
RUN pip install -r /base.txt

RUN mkdir /workspace

# Set workdir for compose file's manage.py
WORKDIR /workspace/cisite

##
# Create dev image
##
FROM base as dev

RUN apt-get -y install python3-coverage
RUN pip install pre-commit

RUN pip install -r /local.txt

##
# Create prod image
##
FROM base as prod

RUN apt-get -y install apache2-dev

RUN pip install -r /production.txt
