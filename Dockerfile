##
# Create base image for prod and dev
##
FROM python:3.6 as base

ENV PYTHONUNBUFFERED 1
ENV PIPENV_VENV_IN_PROJECT 1

RUN pip install pipenv

RUN apt-get -y update
RUN apt-get -y install libldap2-dev libsasl2-dev curl gnupg apache2-dev

RUN curl -sL https://deb.nodesource.com/setup_11.x | bash -
RUN apt-get -y install nodejs

RUN mkdir /workspace

COPY . /workspace

WORKDIR /workspace

##
# Create dev image
##
FROM base as dev

RUN pipenv install --dev
RUN npm install

WORKDIR /workspace/cisite

##
# Create prod image
# WIP
##
FROM base as prod

RUN pipenv install
RUN npm install --production
RUN npm run build

WORKDIR /workspace/cisite
