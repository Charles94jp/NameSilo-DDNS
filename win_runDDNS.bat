@echo off
:: %0为bat文件目录，d向前扩展到驱动器，p往后扩展到路径。即进入bat文件的文件夹，避免开机时运行的目录不对
cd  %~dp0
for /f "tokens=2 delims=:" %%i in ('find /i "key" _conf.txt') do ( set ddnskey=%%i )
for /f "tokens=2 delims=:" %%i in ('find /i "domain" _conf.txt') do ( set ddnsdomain=%%i )
for /f "tokens=2 delims=:" %%i in ('find /i "frequency" _conf.txt') do ( set ddnsfrequency=%%i )

java -jar DDNSjar.jar %ddnskey% %ddnsdomain% %ddnsfrequency%
pause