<h1 align="center">
  <img src="logo.svg" width="300px">
  <br>
</h1>

<p align="center">
<a href="https://github.com/Charles94jp/NameSilo-DDNS/tree/python"><img src="https://img.shields.io/badge/NameSilo-DDNS-brightgreen"></a>  
<a target="_blank" href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-_red.svg"></a>  
<a href="#----"><img src="https://img.shields.io/badge/python-v3.8-blue"></a>
</p>

<h4 align="center">简体中文 | <a href="https://github.com/Charles94jp/NameSilo-DDNS/blob/python/readme.md">English</a></h3>


NameSilo DDNS是一个用于NameSilo域名的DDNS服务，适用于家庭宽带，它能自动检测家庭宽带的IP变动，并自动更新域名的解析。

本项目已通过python3重构，查看Java版本请切换分支。

本程序仅适用于NameSilo上购买的域名

本程序通过访问 http://202020.ip138.com/ 获取家庭宽带的公网IP地址，通过 https://www.namesilo.com/api/ 来查询和更新DNS状态。

右上角点个 ⭐ Star 不迷路

## Features

- 配置简单，可设置检测IP和刷新域名解析的频率

- 具有邮件提醒功能，服务长时间运行过程中的掉线提醒

- 支持多平台Linux,Windows...

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

目前运营商给家庭宽带的IP都是动态的，庆幸的是虽然IP地址不固定，但分配到家庭路由器的却是一个实实在在的公网IP，所以我们只需使用**路由器NAT映射**（需要路由器支持，在管理台设置）即可在公网访问家庭的设备。我们路由器映射22端口就能远程家里的linux，映射445+3389端口就能用win10自带远程桌面远程家里的windows。如下图

![网络拓扑图](https://raw.githubusercontent.com/Charles94jp/NameSilo-DDNS/java/Network-topology.png)

为解决公网IP的变动，可以购买一个域名，使用DDNS（Dynamic Domain Name Server，动态域名服务）将域名解析到宽带的IP。这样就可以在家搭建各种服务并通过访问固定的域名来访问，而无需租用昂贵的公网服务器

想实现这个目的，你需要一台一直运行的电脑来运行此DDNS程序



## Install

下载即用

```
git -b python clone https://github.com/Charles94jp/NameSilo-DDNS.git
```

更新程序：

```
mv conf.json conf.json.back
git pull origin python
mv conf.json.back conf.json
```

### Dependencies


需要使用python3来运行，python需要安装httpx模块：

```
pip install httpx
```

## Usage

### Configuration

启动前需要配置conf.json文件

|字段|介绍|
|--|--|
|domain|要更新的域名，必须是子域名，如你购买的域名是bb.cc，你必须在NameSilo上建一个子域名的解析，如aa.bb.cc| 
|key|<a target="_blank" href="https://guozh.net/obtain-namesilo-api-key/">从NameSilo获取</a>的api key，有key才能获取和修改你的域名状态，保管好不要泄露此key| 
|frequency|多久检测一次你的ip变动，如有变动才更新你的域名解析状态，单位s| 
|mail_host|SMT邮件服务器，如qq、163等| 
|mail_port|邮件服务器端口| 
|mail_user|登录用户名，也是发件人| 
|mail_pass|登录密码或key| 
|receivers|数组，收件人地址，可以是多个| 

关于邮件提醒：简单地说就是出bug后用mail_user给receivers发送一个提醒邮件。避免IP变动后无法用域名访问。

所有邮件参数都是可选的，如少填一个，程序错误时都不会发送邮件提醒。 以qq邮箱为例，如果想用qq邮箱发送邮件，需要进邮箱开启SMTP服务，并获得一个用于登录的key，在帮助里找到服务对应的服务器即可。收件人地址不限于qq邮箱平台，收件人也可以是发件人

### Note


本程序只能更新域名的DNS记录，无法增加，请确保你的域名存在此DNS记录，且需要是一个子域名。

### Start


直接启动：

```
python ddns.py
```

linux置于后台：

```
nohup python ddns.py &
# 杀死进程
ps -ef|grep ddns.py|grep -v grep|cut -c 9-15|xargs kill -9
```

### Start At Boot

<b>Linux</b>

设置开机启动，仅示范CentOS 7，其他Linux发行版请自行编写脚本。

首先编辑DDNS文件，修改第8行为NameSilo-DDNS项目路径，修改第17行为python 3可执行文件路径

接着将DDNS注册为服务：

```
chmod +x DDNS
cp DDNS /etc/init.d/DDNS
chkconfig --add /etc/init.d/DDNS
# 查看是否注册成功
chkconfig --list
```

注册DDNS为服务后，即完成了开机自动启动设置，且可以通过`service`使用DDNS：

```
service DDNS {start|stop|status|restart|force-reload}
```


<b>Windows</b>

将vbs文件[加入策略组](https://blog.csdn.net/yunmuq/article/details/110199091)
