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
</p>

<h4 align="center">简体中文 | <a href="https://github.com/Charles94jp/NameSilo-DDNS#----">English</a></h3>


NameSilo DDNS是一个用于NameSilo的动态域名解析服务，适用于家庭宽带，它能自动检测家庭宽带的IP变动，并自动更新域名的解析。

本项目已通过python3重构，查看Java版本请切换分支。

本程序仅适用于NameSilo上购买的域名

本程序通过访问 http://2021.ip138.com/ 获取家庭宽带的公网IP地址，通过 https://www.namesilo.com/api/ 来查询和更新DNS状态。

右上角点个 ⭐ Star 不迷路

# Features

- 配置简单，可设置检测IP和刷新域名解析的频率

- 日志记录和归档

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
- [Links](#links)

# Background

目前运营商给家庭宽带的IP都是动态的，庆幸的是虽然IP地址不固定，但分配到家庭路由器的却是一个实实在在的公网IP，所以我们只需使用**路由器NAT映射**（需要路由器支持，在管理台设置）即可在公网访问家庭的设备。我们路由器映射22端口就能远程家里的linux，映射445+3389端口就能用win10自带远程桌面远程家里的windows。如下图

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
mv conf.json conf.json.back
git pull origin python
mv conf.json.back conf.json
```

## Dependencies


需要使用python3来运行，python需要安装httpx模块：

```
pip install httpx
```

# Usage

## Configuration

启动前需要配置conf.json文件，只有前两配置个是必要的，其余的可以不配置。

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

关于邮件提醒：简单地说就是程序意外停止后用mail_user给receivers发送一个提醒邮件，避免IP变动后未更新DNS，导致无法用域名访问。

Q：什么情况下程序会意外停止？

A：我会避免程序本身的编码出bug，但是使用的api可能会出错，比如NameSilo的api或ip138的api无法连接，这是可能发生的。

所有邮件参数都是可选的，如少填一个，程序错误时都不会发送邮件提醒。 以qq邮箱为例，如果想用qq邮箱发送邮件，需要进邮箱开启SMTP服务，并获得一个用于登录的key，在帮助里找到服务对应的服务器即可。收件人地址不限于qq邮箱平台，收件人也可以是发件人

## Note


本程序只能更新域名的DNS记录，无法增加，请确保你的域名存在此DNS记录，且需要是一个子域名。

## Start


**直接启动：**

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

<b>Linux</b>

查看日志文件

```
ls -lh DDNS*.log*
```

其中`DDNS.log`是当前最新的日志文件，其余的为`gzip`压缩过的归档文件。当DDNS服务启动时，若`DDNS.log`超过2M便会触发自动归档。可以存储使用DDNS以来所有的日志。

解压归档文件：

```
gunzip -N DDNS-xxx.log.gz
```

解压后即可阅读

<b>Windows</b>

当DDNS服务启动时，若`DDNS.log`超过2M便会将旧的`DDNS.log`文件重命名为`DDNS-xxx.log.back`，不会压缩

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

# Links

相关链接：

- NameSilo API Document: [Domain API Reference - NameSilo](https://www.namesilo.com/api-reference#dns/dns-list-records)

- 当前IP查询: [ip138.com](https://www.ip138.com/)