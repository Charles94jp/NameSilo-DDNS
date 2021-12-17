import json
import logging
import os
import time
import smtplib
from email.mime.text import MIMEText

import httpx


class DDNS:
    ## 通过配置文件初始化
    key = ''
    # 配置中domain = host.domain，host为子域名前缀
    domain = ''
    host = ''
    frequency = 600
    emailAlert = False
    mail_host = ''
    mail_port = ''
    mail_user = ''
    mail_pass = ''
    receivers = []

    ## 运行中调用
    apiRoot = "https://www.namesilo.com/api"
    getIp = "http://2021.ip138.com/"
    domainIp = ''
    currentIp = ''
    logger = None
    httpHeaders = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                 'Chrome/96.0.4664.93 Safari/537.36'}
    rrid = ''
    errorCount = 0

    def __init__(self, args, debug=False):
        """
        set attributes，set logger
        :param args: dict
        """
        self.key = args['key']
        tmp = args['domain']
        tmp = tmp.split('.')
        self.domain = tmp[-2] + '.' + tmp[-1]
        self.host = tmp[0]
        if args.get('frequency'):
            self.frequency = args['frequency']

        if args['mail_host'] and args['mail_port'] and args['mail_user'] and args['mail_pass'] and args['receivers']:
            self.emailAlert = True
            self.mail_host = args['mail_host']
            self.mail_port = args['mail_port']
            self.mail_user = args['mail_user']
            self.mail_pass = args['mail_pass']
            self.receivers = args['receivers']

        if os.path.isfile('DDNS.log'):
            if os.path.isfile('DDNS.log.back'):
                os.remove('DDNS.log.back')
            os.rename('DDNS.log', 'DDNS.log.back')
        self.logger = logging.getLogger('DDNS')  # 传logger名称返回新logger，否则返回root，会重复输出到屏幕
        self.logger.setLevel(logging.INFO)
        fh = logging.FileHandler(filename='DDNS.log', encoding='utf-8', mode='w')
        formatter = logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s")
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        if debug:
            fh = logging.StreamHandler()
            self.logger.addHandler(fh)
        self.logger.info('starting...')

    def get_current_ip(self):
        """
        update self.currentIp
        :return: None
        """
        r = httpx.get(self.getIp, headers=self.httpHeaders, timeout=10)
        if r.status_code == 200:
            r = r.text
            r = r.split('您的IP地址是：')[1]
            r = r.split('</title>')[0]
            self.currentIp = r
            self.logger.info("get_current_ip: \tcurrent host ip: " + r)
        else:
            self.logger.error("get_current_ip: \tapi error")

    def get_domain_ip(self):
        """
        update self.domainIp
        :return: None
        """
        r = httpx.get(self.apiRoot + '/dnsListRecords?version=1&type=xml&key=' + self.key + '&domain=' + self.domain,
                      timeout=10)
        if r.status_code == 200:
            r = r.text.split('<resource_record>')
            for record in r:
                if record.find(self.host + '.' + self.domain) != -1:
                    r = record
                    break
            r = r.split('</record_id>')
            self.rrid = r[0].split('<record_id>')[-1]
            self.domainIp = r[1].split('<value>')[1].split('</value>')[0]
            self.logger.info("get_domain_ip: \tcurrent domain name resolution ip: " + self.domainIp)
        else:
            self.logger.error("get_domain_ip: \tapi error")

    def update_domain_ip(self, new_ip):
        """
        更新域名解析，更新self.domainIp
        :return: None
        """
        r = httpx.get(
            self.apiRoot + '/dnsUpdateRecord?version=1&type=xml&rrttl=7207&key=' + self.key + '&domain=' + self.domain
            + '&rrid=' + self.rrid + '&rrhost=' + self.host + '&rrvalue=' + new_ip,
            timeout=10)
        r = r.text
        r = r.split('<code>')[1]
        r = r.split('</code>')[0]
        if r == '300':
            self.domainIp = new_ip
            self.logger.info("update_domain_ip: \tupdate completed: " + self.domainIp)
        else:
            self.logger.error("update_domain_ip: \tupdate failed")

    def send_email(self, html_msg):
        # 邮件消息，plain是纯文本，html可以自定义样式
        message = MIMEText(html_msg, 'html', 'utf-8')
        # 邮件主题
        message['Subject'] = 'DDNS服务异常提醒'
        # 发送方信息
        message['From'] = self.mail_user
        # 接受方信息
        message['To'] = ','.join(self.receivers)

        # 登录并发送邮件
        try:
            smtpObj = smtplib.SMTP()
            # 连接到服务器
            smtpObj.connect(self.mail_host, 25)
            # 登录到服务器
            smtpObj.login(self.mail_user, self.mail_pass)
            # 发送
            smtpObj.sendmail(
                self.mail_user, self.receivers, message.as_string())
            # 退出
            smtpObj.quit()
            self.logger.info("send_email: \tsuccess")
        except smtplib.SMTPException as e:
            ddns.logger.exception(e)

    def start(self):
        self.get_domain_ip()
        last_error = False
        while True:
            try:
                self.get_current_ip()
                if self.currentIp != self.domainIp:
                    self.update_domain_ip(self.currentIp)
                last_error = False
            except BaseException as e:
                ddns.logger.exception(e)
                if last_error:
                    self.errorCount = self.errorCount + 1
                else:
                    self.errorCount = 1
                if self.errorCount > 10:
                    if self.emailAlert:
                        self.send_email('<p class="MsoNormal"><span style="font-family:宋体;color:black">您好！</span></p>'
                                        '<p class="MsoNormal" style="text-indent:21.0pt"><span style="font-family:宋体;'
                                        'color:black">您的DDNS服务因异常已停止，这并非是服务本身导致的，可能是ip138.com或NameSilo的api'
                                        '繁忙所致。</span></p><p class="MsoNormal" style="text-indent:21.0pt"><span '
                                        'style="font-family:宋体;color:black">您可以DDNS.log文件查看异常细明，<b>请尽快排查原因'
                                        '并重启DDNS服务</b>，避免IP变动导致您的服务器无法通过域名访问。</span></p><p class="MsoNormal"'
                                        ' style="text-indent:21.0pt"><span style="font-family:宋体;color:black">有任何问题请在'
                                        '<a target="_blank" href="https://github.com/Charles94jp/NameSoli-DDNS">DDNS项目的'
                                        'GitHub Issues</a>中反馈，谢谢您的支持</span></p>')
                    self.logger.error("start: \t连续错误10次，程序退出")
                    break
            time.sleep(self.frequency)


if __name__ == '__main__':
    """
    不要开代理、梯子，会http连接错误
    """
    ddns = None
    try:
        with open('conf.json', 'r') as fp:
            ddns = DDNS(json.load(fp))
        ddns.start()
    except BaseException as e:
        ddns.logger.exception(e)