#!/opt/local/bin/python
"""

　　┏┓　　　┏┓+ +
　┏┛┻━━━┛┻┓ + +
　┃　　　　　　　┃ 　
　┃　　　━　　　┃ ++ + + +
 ████━████ ┃+
　┃　　　　　　　┃ +
　┃　　　┻　　　┃
　┃　　　　　　　┃ + +
　┗━┓　　　┏━┛
　　　┃　　　┃　　　　　　　　　　　
　　　┃　　　┃ + + + +
　　　┃　　　┃
　　　┃　　　┃ +  神兽保佑
　　　┃　　　┃    代码无bug　　
　　　┃　　　┃　　+　　　　　　　　　
　　　┃　 　　┗━━━┓ + +
　　　┃ 　　　　　　　┣┓
　　　┃ 　　　　　　　┏┛
　　　┗┓┓┏━┳┓┏┛ + + + +
　　　　┃┫┫　┃┫┫
　　　　┗┻┛　┗┻┛+ + + +


Author: Yiqian Qian
Description: file content
Date: 2021-10-24 19:00:37
LastEditors: Yiqian Qian
LastEditTime: 2021-10-30 20:03:46
FilePath: /undefined/Users/qyq/Library/Mobile Documents/com~apple~CloudDocs/Development/量化交易/quantitative/lesson2/sendmail.py
"""
# -*- coding: UTF-8 -*-


import smtplib
import time
import traceback
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import requests

my_sender = "qyqstc@163.com"  # "664777536@qq.com"  # 发件人邮箱账号
my_pass = "HXYYABTYMLOAAOAA"  # "tolmxmykjruxbfaj"  # 发件人邮箱密码
my_user = [
    "qyqstc@gmail.com",
    "kevinfuc@163.com",  # 付聪
    "yxtccty@163.com",  # 小崔
    # "121841596@qq.com",
    "1061559807@qq.com",  # 砖头哥
    "80380573@qq.com",  # 老姐
    # "a77ccc@163.com",
    # 'jwanzi@qq.com',
    "627981326@qq.com",  # 周总
    # "yxwy1018@163.com",  # 老妈
    "taoxuan@hust.edu.cn",  # 小桃
]  # 收件人邮箱账号


def mail(message):
    ret = True
    for user in my_user:
        try:
            current_dt = time.strftime("%Y-%m-%d", time.localtime())
            # current_dt = datetime.strptime(current_dt, '%Y-%m-%d')
            title = current_dt.split(" ")[0] + "投资操作"
            msg = MIMEMultipart()
            content = MIMEText(message, "plain", "utf-8")
            msg.attach(content)

            img1 = MIMEImage(
                open("rank_stock_scores.png", "rb").read(), _subtype="octet-stream"
            )
            img1.add_header(
                "Content-Disposition", "attachment", filename="rank-stock-scores.png"
            )
            msg.attach(img1)

            img2 = MIMEImage(
                open("同花顺/heatmap.html", "rb").read(), _subtype="octet-stream"
            )
            img2.add_header(
                "Content-Disposition", "attachment", filename="heatmap.html"
            )
            msg.attach(img2)
            img3 = MIMEImage(
                open("同花顺/5day_ret.html", "rb").read(), _subtype="octet-stream"
            )
            img3.add_header(
                "Content-Disposition", "attachment", filename="5day_ret.html"
            )
            msg.attach(img3)
            img4 = MIMEImage(
                open("rank_stock_variations.png", "rb").read(), _subtype="octet-stream"
            )
            img4.add_header(
                "Content-Disposition",
                "attachment",
                filename="rank_stock_variations.png",
            )
            msg.attach(img4)

            img5 = MIMEImage(
                open("同花顺/treemap.html", "rb").read(), _subtype="octet-stream"
            )
            img5.add_header(
                "Content-Disposition", "attachment", filename="treemap.html"
            )
            msg.attach(img5)

            img6 = MIMEImage(
                open("rank_stock_variations_120.png", "rb").read(),
                _subtype="octet-stream",
            )
            img6.add_header(
                "Content-Disposition",
                "attachment",
                filename="rank_stock_variations_120.png",
            )
            msg.attach(img6)

            img7 = MIMEImage(
                open("rank_stock_scores_120.png", "rb").read(), _subtype="octet-stream"
            )
            img7.add_header(
                "Content-Disposition",
                "attachment",
                filename="rank_stock_scores_120.png",
            )
            msg.attach(img7)

            with open("rank_stock.csv", "rb") as f:
                file = MIMEApplication(f.read())
                file.add_header(
                    "Content-Disposition", "attachment", filename="rank_stock.csv"
                )
                msg.attach(file)

            msg["From"] = formataddr(["量化精灵", my_sender])  # 发件人昵称
            msg["To"] = formataddr(["Master", user])  # 接收人昵称
            msg["Subject"] = title  # 邮件的主题

            # 发件人邮箱中的SMTP服务器, 端口是465
            server = smtplib.SMTP_SSL("smtp.163.com", 465)
            server.login(my_sender, my_pass)  # 发件人邮箱账号、邮箱密码
            # 发件人邮箱账号、收件人邮箱账号、发送邮件
            server.sendmail(
                my_sender,
                [
                    user,
                ],
                msg.as_string(),
            )
            server.quit()  # 关闭连接
        except Exception as e:  # 如果 try 中的语句没有执行，则会执行下面的 ret = False
            ret = False
            print(e)
    return ret


def send_wechat(message):
    ret = True
    try:
        token = "8935374ce77e496992cce6d226ccf567"
        topic = "1"
        title = "量化精灵"
        content = message
        template = "html"
        url = f"https://www.pushplus.plus/send?token={token}&title={title}&content={content}&template={template}&topic={topic}"
        print(url)
        r = requests.get(url=url)
        # print(r.text)
    except Exception as e:
        ret = False
        print(e)
    return ret


if __name__ == "__main__":
    message = """
    这是120分钟数据
今日自选股: 深中华A 注意：3日线下叉10日线，分数连续下降1，赶快跑路！
今日自选股: 中基健康 相信自己，冲冲冲！
今日自选股: 中马传动 相信自己，冲冲冲！
今日自选股: 中视传媒 相信自己，冲冲冲！
今日自选股: 长白山 注意：3日线下叉10日线，分数连续下降5，赶快跑路！
今日大盘信号：SELL！


祝大家股路长盈!
********************极速上升股********************
极速之星: 克来机电 上涨 2.746622199402085
极速之星: 大立科技 上涨 2.2284547331750932
极速之星: 中国神华 上涨 1.5720408758549265
极速之星: 中国中免 上涨 1.4805681119317313
极速之星: 凤凰传媒 上涨 1.2887396563778855
********************备选股********************

深中华A(000017):54.070833595192504

中基健康(000972):14.042292797261386

中马传动(603767):7.534217479550314

中视传媒(600088):5.975427923686955

长白山(603099):3.701483785812384

包钢股份(600010):3.5215867974740322

哈森股份(603958):3.260515356289757

金证股份(600446):3.2009370150209273

克来机电(603960):2.8554548751472972

大立科技(002214):2.235580238391656

中国广核(003816):2.05386165855854

浦东金桥(600639):1.9980465037213186

凤凰传媒(601928):1.8828204779583064

海航控股(600221):1.8408988316259791

工商银行(601398):1.6988530685478984

中国神华(601088):1.5734673644464434

北京银行(601169):1.5733855655224362

中煤能源(601898):1.5700996933213418

海信家电(000921):1.496466921758805

浙能电力(600023):1.4130854861940736

农业银行(601288):1.3931429087826936

食用方式：当第一只股是'冲冲冲'并且大盘信号也是'买买买'时，只买入排名第一的股，后面几只仅供参考;当大盘信号或个股信号只要其中之一是跑路，就 卖出。极速之星是每日评分上升最快的股，可以留意观察机会。
    """
    ret = send_wechat(message)
    if ret:
        print("发送成功")
    else:
        print("发送失败")
