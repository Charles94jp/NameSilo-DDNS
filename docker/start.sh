#!/bin/sh
if [ -d "/home/NameSilo-DDNS" ]; then
    cp /home/NameSilo-DDNS.back/ddns.py /home/NameSilo-DDNS/ddns.py
    cp -r /home/NameSilo-DDNS.back/lib /home/NameSilo-DDNS/
    cp /home/NameSilo-DDNS.back/ddns-docker /home/NameSilo-DDNS/ddns-docker
    chmod +x /home/NameSilo-DDNS/ddns-docker
    cp -r /home/NameSilo-DDNS.back/conf /home/NameSilo-DDNS/
    mkdir -p /home/NameSilo-DDNS/log
    cd /home/NameSilo-DDNS
fi

while true
do
    ddns_ps=`ps -ef|grep ddns|grep -v grep`
    if [ -z "$ddns_ps" ]
    then
        nohup python /home/NameSilo-DDNS/ddns.py >> /home/NameSilo-DDNS/log/DDNS.log 2>&1 &
    fi
    sleep 666
done
