FROM python:3.8.12-alpine3.15
LABEL maintainer="https://github.com/Charles94jp/NameSilo-DDNS"
LABEL description="NameSilo-DDNS"

COPY ddns.py /home/NameSilo-DDNS.back/ddns.py
COPY conf/ /home/NameSilo-DDNS.back/conf/
COPY docker/start.sh /start.sh

RUN pip install httpx \
    && chmod 777 /start.sh

CMD ["/start.sh"]