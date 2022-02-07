@echo off
:: %0为bat文件目录，d向前扩展到驱动器，p往后扩展到路径。即进入bat文件的文件夹，避免开机时运行的目录不对
cd  %~dp0

python ..\ddns.py
pause