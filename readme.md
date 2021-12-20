<h1 align="center">
  <img src="logo.svg" width="300px">
  <br>
</h1>

<p align="center">
<a href="https://github.com/Charles94jp/NameSilo-DDNS/tree/python"><img src="https://img.shields.io/badge/NameSilo-DDNS-brightgreen"></a>  
<a target="_blank" href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-_red.svg"></a>  
<a href="#----"><img src="https://img.shields.io/badge/python-v3.8-blue"></a>
</p>

<h4 align="center"><a href="https://github.com/Charles94jp/NameSilo-DDNS/blob/python/readme.zh-CN.md">简体中文</a> | English</h3>


NameSilo DDNS is a DDNS service for NameSilo domain names for home broadband , it can automatically detect IP changes in home broadband and automatically update the resolution of the domain name.

This project has been refactored via Python3, to view the Java version please switch branches.

This program is only available for domain names purchased on NameSilo.

This program obtains the public IP address of home broadband by visiting http://202020.ip138.com/, and queries and updates the DNS status by https://www.namesilo.com/api/.

It would be the best encouragement for me to get your  ⭐ STAR.

## Features

- Simple configuration, you can set the frequency of detecting IP changes and refreshing DNS.

- With email alert function, you will be alerted when there is an abnormality in the process of the service running for a long time.

- Support multi-platform (Linux, Windows...)

## Table of Contents

- [Background](#background)
- [Install](#install)
    - [Dependencies](#dependencies)
- [Usage](#usage)
    - [Configuration](#configuration)
    - [Note](#note)
    - [Start](#start)
    - [Start At Boot](#start-at-boot)

## Background

At present, telecom operators assign to home broadband IP are dynamic, although the IP address is not fixed, but the good thing is that the home router can get a real public IP, so we just need to use **router NAT mapping** (need router support, set up in the management console) to access the home device in the public network. After the router mapping port 22 we can remotely connect to our home linux machine, and after mapping port 445+3389 we can use the remote desktop of Win10.

![网络拓扑图](https://raw.githubusercontent.com/Charles94jp/NameSilo-DDNS/java/Network-topology.png)

To solve the problem of changing public IP, you can purchase a domain name and use DDNS (Dynamic Domain Name Server) to resolve the domain name to your broadband's IP. This will allow you to access your home devices by accessing a fixed domain name.

To achieve this, you need a computer that is always running to run this DDNS program.


## Install

Download and use

```
git -b python clone https://github.com/Charles94jp/NameSilo-DDNS.git
```

Update

```
mv conf.json conf.json.back
git pull origin python
mv conf.json.back conf.json
```

### Dependencies


A Python3 environment is required. The httpx module also needs to be installed.

```
pip install httpx
```

## Usage

### Configuration

The conf.json file needs to be configured before starting.

|Fields|Introduction|
|--|--|
|domain|The domain name to be updated must be a subdomain. For example, if you purchase a domain name that is bb.cc, you must build a resolution on NameSilo for a subdomain such as aa.bb.cc.| 
|key|<a target="_blank" href="https://www.namesilo.com/account/api-manager">The key generated from NameSilo</a>, after generation you need to remember and keep this key.| 
|frequency|How often do you detect changes in your ip, and only update your DNS when a change in ip occurs, in seconds.| 
|mail_host| For example, you can use Google Mail's POP/IMAP | 
|mail_port| | 
|mail_user|The login user name, which is also the email sender.| 
|mail_pass|passwd or key| 
|receivers|An array to hold the recipient's address.| 

The last five configurations are not required. Only after all five are filled in will the email alert feature be enabled.

### Note


This program can only update the DNS record of a domain name, it cannot be added, please make sure this DNS record exists for your domain name and it needs to be a sub-domain.

### Start


Direct start

```
python ddns.py
```

Linux usage:

```
./DDNS {start|stop|status|restart|force-reload}
```

Example
![](example.png)

Windows usage: Double-click the bat or vbs file, please check the log for the running status of the program.

### Start At Boot

<b>Linux</b>

Set up start at boot, only CentOS 7 is demonstrated, please write your own script for other Linux distributions.

First edit the DDNS file, change the 8th line to the path of NameSilo-DDNS project, change the 17th line to the path of python 3 executable file

Next, register DDNS as a service.

```
chmod +x DDNS
cp DDNS /etc/init.d/DDNS
chkconfig --add /etc/init.d/DDNS
# check
chkconfig --list
```

After registering DDNS as a service, you have finished setting the start at boot and you can use DDNS through `service`.

```
service DDNS {start|stop|status|restart|force-reload}
```


<b>Windows</b>

Add the vbs file to the Windows policy group.
