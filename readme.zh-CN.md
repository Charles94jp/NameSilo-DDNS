<h1 align="center">
  <a href="#">
  <img src="logo.svg" width="300px">
  </a>
  <br>
</h1>

<p align="center">
<a href="https://github.com/Charles94jp/NameSilo-DDNS/tree/python"><img src="https://img.shields.io/badge/NameSilo-DDNS-brightgreen"></a>  
<a target="_blank" href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-_red.svg"></a>  
<a href="#python3"><img src="https://img.shields.io/badge/python-v3.8-blue"></a>
<a href="#table-of-contents"><img src="https://img.shields.io/badge/Docker-Build-brightgreen"></a>
<a href="#features"><img src="https://img.shields.io/badge/multi-platform-orange"></a>
<a href="#features"><img src="https://img.shields.io/badge/log-rotation-orange"></a>
</p>

<h4 align="center">简体中文 | <a href="https://github.com/Charles94jp/NameSilo-DDNS#----">English</a></h3>


NameSilo DDNS是一个用于NameSilo的动态域名解析服务，适用于家庭宽带，它能自动检测家庭宽带的IP变动，并自动更新域名的解析。

本项目已通过python3重构，查看Java版本请切换分支。

本程序仅适用于NameSilo上购买的域名

本程序通过访问 http://202x.ip138.com 或https://api.myip.com 或 https://api.ipify.org?format=json获取家庭宽带的公网IP地址，通过 https://www.namesilo.com/api/ 来查询和更新DNS状态。

右上角点个 ⭐ Star 不迷路

# Features

- 配置简单，可设置检测IP和刷新域名解析的频率

- 日志记录和滚动

- 具有邮件提醒功能，服务长时间运行过程中的掉线提醒

- 支持多平台Linux,Windows...

# Table of Contents

- [Background](#background)
- [Install](#install)
    - [Dependencies](#dependencies)
- [Usage](#usage)
    - [Configuration](#configuration)
    - [Note](#note)
    - [Start](#start)
    - [Log](#log)
    - [Start At Boot](#start-at-boot)
- [Docker](#Docker)
    - [Build or Pull Image](#build-or-pull-image)
    - [RUN](#run)
    - [Start with Linux](#start-with-linux)

- [Links](#links)

# Background

目前运营商给家庭宽带的IP都是动态的，庆幸的是虽然IP地址不固定，但分配到家庭路由器的却是一个实实在在的公网IP，所以我们只需**设置光猫桥接模式 + 路由器拨号上网 + 路由器NAT映射/DMZ主机**即可在公网访问家庭的设备。

需要几个前提条件：

- 路由器支持NAT映射/DMZ主机功能，有的路由器甚至支持DDNS，不过是指定域名厂商的，一般是花生壳，也是需要备案的。所以本项目对比路由器自带DDNS仍有优势

- 获取宽带的账号密码，拨号时使用

- 获取光猫超级用户的账号密码，用于设置桥接模式，这个根据光猫型号去网上搜即可

一切顺利的话，我们路由器映射22端口就能远程家里的linux，映射445+3389端口就能用win10自带远程桌面远程家里的windows。如下图

![网络拓扑图](https://raw.githubusercontent.com/Charles94jp/NameSilo-DDNS/java/Network-topology.png)

为解决公网IP的变动，可以购买一个域名，使用DDNS（Dynamic Domain Name Server，动态域名服务）将域名解析到宽带的IP。这样就可以在家搭建各种服务并通过访问固定的域名来访问，而无需租用昂贵的公网服务器

想实现这个目的，你需要一台一直运行的电脑来运行此DDNS程序



# Install

下载即用

```
git -b python clone https://github.com/Charles94jp/NameSilo-DDNS.git
```

更新程序：

```
git pull origin python
```

## Dependencies


需要使用python3来运行，python需要安装httpx模块：

```
pip install httpx
```

# Usage

## Configuration

启动前需要配置`conf/conf.json`文件，参考conf.json.example，**只有前两项配置是必要的**，其余的可以不进行配置。

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
|email_after_reboot|前提：Linux，设置了邮件，设置了开机启动。默认false，设置为true后，如果系统开机时间距离上次关机时间大于4分钟，且DDNS启动时间距离开机时间小于4分钟，会收到邮件提醒，获得当前IP。<br>适用于家里意外断电的情况，当通电后，路由器重新拨号，一般会获得新IP，如果服务器支持来电自动开机，那么DDNS在开机自动启动后，会发送邮件告诉你：你的服务器已成功启动。|
|auto_restart|Linux下生效，默认不启用。在程序持续异常一段时间后，自我重启。因为服务在长时间运行后，向NameSilo发起https请求时，会出现异常，目前不知道原因，但是重启DDNS能解决问题。|

关于邮件提醒：简单地说就是程序意外停止后用mail_user给receivers发送一个提醒邮件，避免IP变动后未更新DNS，导致无法用域名访问。

Q：什么情况下程序会意外停止？

A：我会避免程序本身的编码出bug，但是使用的api可能会出错，比如NameSilo的api或ip138的api无法连接，这是可能发生的。

所有邮件参数都是可选的，如少填一个，程序错误时都不会发送邮件提醒。 以qq邮箱为例，如果想用qq邮箱发送邮件，需要进邮箱开启SMTP服务，并获得一个用于登录的key，在帮助里找到服务对应的服务器即可。收件人地址不限于qq邮箱平台，收件人也可以是发件人

测试邮件设置是否正确，会发送一封邮件到你的邮箱：

```
DDNS testEmail
# or
python ddns.py testEmail
```

## Note


本程序只能更新域名的DNS记录，无法增加，请确保你的域名存在此DNS记录，且需要是一个子域名。

## Start

**快速启动：**

```
python ddns.py
```

**Linux高级使用：**

首先编辑DDNS文件，修改第8行为NameSilo-DDNS项目路径，修改第17行为python 3可执行文件路径即可使用

```
chmod +x DDNS
# usage
./DDNS {start|stop|status|restart|force-reload}
```

例如

![](example.png)

如果想在任何地方使用`DDNS`命令，可以在`/usr/bin`目录下建立软链接，注意`ln`命令要使用绝对路径，如

```
ln -s /root/NameSilo-DDNS/DDNS /usr/bin/DDNS
```

**Windows使用：** 双击bat或vbs文件，程序运行状态请查看日志

## Log

日志都在log文件夹下

<b>Linux</b>

查看日志文件

```
ls -lh log/DDNS*.log*
```

其中`DDNS.log`是当前最新的日志文件，其余的为`gzip`压缩过的归档文件。当DDNS服务启动时，若`DDNS.log`超过2M便会触发自动归档。可以存储使用DDNS以来所有的日志。

解压归档文件：

```
gunzip -N DDNS-xxx.log.gz
```

解压后即可阅读

手动归档日志，用于在`DDNS status`打印信息过多时

```
DDNS archiveLog
```

<b>Windows</b>

当DDNS服务启动时，若`DDNS.log`超过2M便会将旧的`DDNS.log`文件重命名为`DDNS-xxx.log.back`，不会压缩

手动归档日志:

```
python ddns.py archiveLog
```

## Start At Boot

<b>Linux</b>

设置开机启动，仅示范RedHat系列，如CentOS 7 8和Rocky Linux 8，其他Linux发行版请自行编写脚本。

将DDNS注册为systemctl管理的服务

首先要按照[start](#start)中的步骤配置DDNS文件

接着配置DDNS.service文件，修改其中DDNS文件的路径，最后

```
cp  ./DDNS.service  /usr/lib/systemd/system/DDNS.service
systemctl daemon-reload
systemctl enable DDNS
```

<b>Windows</b>

将vbs文件[加入策略组](https://blog.csdn.net/yunmuq/article/details/110199091)



# Docker

现在，NameSilo-DDNS支持docker启动了（Linux），不需要本机有python环境，在开机启动方面也不用systemctl了

## Build or Pull Image

<b>Docker Hub</b>

>  请期待

本镜像基于最小的Linux alpine构建，镜像大小为57M

Docker Hub中的镜像只会随release更新，不一定是最新的，你也可以选择手动构建镜像

<b>手动构建镜像</b>

```shell
docker build -t charles94jp/ddns .
```

下载`python:3.x.x-alpine`镜像和`pip install httpx`需要一点时间

## RUN

```shell
docker run -d --name ddns -v <local dir>:/home/NameSilo-DDNS:rw charles94jp/ddns
# --restart=always
```

一定要用 -v 参数将本机的目录`<local dir>`挂载到容器内的`/home/NameSilo-DDNS`，容器会将程序文件写出到`<local dir>`

接着在`<local dir>`中配置`conf/conf.json`，参考[Configuration](#configuration)

最后记得重启一下容器，因为最开始`docker run`时没有配置文件，所以ddns程序是没有成功运行的

```shell
docker restart ddns
```

查看ddns程序状态用`<local dir>`中的`ddns-docker`

## Start with Linux

```shell
systemctl enable docker
docker update --restart=always ddns
```



# Links

相关链接：

- NameSilo API Document: [Domain API Reference - NameSilo](https://www.namesilo.com/api-reference#dns/dns-list-records)

- 当前IP查询: [ip138.com](https://www.ip138.com/) ; [myip.com](https://www.myip.com/api-docs/) ; [ipify](https://www.ipify.org/)