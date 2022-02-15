#!/bin/sh
if [ -d "/home/NameSilo-DDNS" ]; then
    cp /home/NameSilo-DDNS.back/ddns.py /home/NameSilo-DDNS/ddns.py
    cp /home/NameSilo-DDNS.back/ddns-docker /home/NameSilo-DDNS/ddns-docker
    chmod +x /home/NameSilo-DDNS/ddns-docker
    cp -r /home/NameSilo-DDNS.back/conf /home/NameSilo-DDNS/
    mkdir -p /home/NameSilo-DDNS/log
    cd /home/NameSilo-DDNS
    nohup python /home/NameSilo-DDNS/ddns.py >> /home/NameSilo-DDNS/log/DDNS.log 2>&1 &
fi

while test "1" = "1"
do
sleep 1000
done
/usr/bin/tail -f -s 10 /dev/null
