FROM python:3.9.13-alpine3.16
LABEL maintainer="https://github.com/Charles94jp/NameSilo-DDNS"
LABEL description="NameSilo-DDNS"

ENV TZ Asia/Shanghai

COPY ddns.py /home/NameSilo-DDNS.back/ddns.py
COPY lib/ /home/NameSilo-DDNS.back/lib/
COPY docker/ddns-docker /home/NameSilo-DDNS.back/ddns-docker
COPY conf/ /home/NameSilo-DDNS.back/conf/
COPY docker/start.sh /start.sh

RUN python -m pip install -i https://mirrors.aliyun.com/pypi/simple/ httpx \
    && chmod 777 /start.sh

CMD ["/start.sh"]
