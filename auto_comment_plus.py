# -*- coding: utf-8 -*-
# @Time : 2022/2/8 20:50
# @Author : @qiu-lzsnmb and @Dimlitter
# @File : auto_comment_plus.py

import argparse
import random
import time

import jieba.analyse
import requests
import yaml
from lxml import etree

import jdspider


# constants
CONFIG_PATH = './config.yml'
ORDINARY_SLEEP_SEC = 10
SUNBW_SLEEP_SEC = 5
REVIEW_SLEEP_SEC = 10
SERVICE_RATING_SLEEP_SEC = 15


# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--dry-run',
                    help='have a full run without comment submission',
                    action='store_true')
args = parser.parse_args()
opts = {
    'dry_run': args.dry_run
}


# logging
jieba.setLogLevel(jieba.logging.INFO)


# parse configurations
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)
ck = cfg['user']['cookie']

headers = {
    'cookie': ck,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36',
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Sec-Fetch-Site': 'same-site',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-User': '?1',
    'Sec-Fetch-Dest': 'document',
    'Referer': 'https://order.jd.com/',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


# 评价生成
def generation(pname, _class=0, _type=1, opts=None):
    opts = opts or {}
    items = ['商品名']
    items.clear()
    items.append(pname)
    for item in items:
        spider = jdspider.JDSpider(item)
        # 增加对增值服务的评价鉴别
        if "赠品" in pname or "非实物" in pname or "增值服务" in pname:
            result = [
                "赠品挺好的。",
                "很贴心，能有这样免费赠送的赠品!",
                "正好想着要不要多买一份增值服务，没想到还有这样的赠品。",
                "赠品正合我意。",
                "赠品很好，挺不错的。",
                "本来买了产品以后还有些担心。但是看到赠品以后就放心了。",
                "不论品质如何，至少说明店家对客的态度很好！",
                "我很喜欢这些商品！",
                "我对于商品的附加值很在乎，恰好这些赠品为这件商品提供了这样的的附加值，这令我很满意。"
                "感觉现在的网购环境环境越来越好了，以前网购的时候还没有过么多贴心的赠品和增值服务",
                "第一次用京东，被这种赠品和增值服物的良好态度感动到了。",
                "赠品还行。"
            ]
        else:
            result = spider.getData(4, 3)  # 这里可以自己改

    # class 0是评价 1是提取id
    try:
        name = jieba.analyse.textrank(pname, topK=5, allowPOS='n')[0]
    except Exception as _:
        name = "宝贝"
    if _class == 1:
        return name
    else:
        comments = ''
        if _type == 1:
            num = 6
        elif _type == 0:
            num = 4
        if len(result) < num:
            num = len(result)
        else:
            num = num
        for i in range(num):
            comments = comments + \
                result.pop(random.randint(0, len(result) - 1))

        return 5, comments.replace("$", name)


# 查询全部评价
def all_evaluate(opts=None):
    opts = opts or {}
    N = {}
    url = 'https://club.jd.com/myJdcomments/myJdcomment.action?'
    req = requests.get(url, headers=headers)
    req_et = etree.HTML(req.text)
    evaluate_data = req_et.xpath('//*[@id="main"]/div[2]/div[1]/div/ul/li')
    # print(evaluate)
    for i, ev in enumerate(evaluate_data):
        na = ev.xpath('a/text()')[0]
        try:
            num = ev.xpath('b/text()')[0]
        except IndexError:
            num = 0
        N[na] = int(num)
    return N


# 普通评价
def ordinary(N, opts=None):
    opts = opts or {}
    Order_data = []
    req_et = []
    for i in range((N['待评价订单'] // 20) + 1):
        url = (f'https://club.jd.com/myJdcomments/myJdcomment.action?sort=0&'
               f'page={i + 1}')
        req = requests.get(url, headers=headers)
        req_et.append(etree.HTML(req.text))
    for i in req_et:
        Order_data.extend(i.xpath('//*[@id="main"]/div[2]/div[2]/table/tbody'))
    if len(Order_data) != N['待评价订单']:
        Order_data = []
        for i in req_et:
            Order_data.extend(i.xpath('//*[@id="main"]/div[2]/div[2]/table'))

    print(f"当前共有{N['待评价订单']}个评价。")
    for i, Order in enumerate(Order_data):
        oid = Order.xpath('tr[@class="tr-th"]/td/span[3]/a/text()')[0]
        oname_data = Order.xpath(
            'tr[@class="tr-bd"]/td[1]/div[1]/div[2]/div/a/text()')
        pid_data = Order.xpath(
            'tr[@class="tr-bd"]/td[1]/div[1]/div[2]/div/a/@href')
        for oname, pid in zip(oname_data, pid_data):
            pid = pid.replace('//item.jd.com/', '').replace('.html', '')

            print(f"\t{i}.开始评价订单\t{oname}[{oid}]")
            url2 = "https://club.jd.com/myJdcomments/saveProductComment.action"
            xing, Str = generation(oname, opts=opts)
            print(f'\t\t评价内容,星级{xing}：', Str)
            data2 = {
                'orderId': oid,
                'productId': pid,  # 商品id
                'score': str(xing),  # 商品几星
                'content': bytes(Str, encoding="gbk"),  # 评价内容
                'saveStatus': '1',
                'anonymousFlag': '1'
            }
            if not opts.get('dry_run'):
                pj2 = requests.post(url2, headers=headers, data=data2)
            time.sleep(ORDINARY_SLEEP_SEC)
    N['待评价订单'] -= 1
    return N


# 晒单评价
def sunbw(N, opts=None):
    opts = opts or {}
    Order_data = []
    for i in range((N['待晒单'] // 20) + 1):
        url = (f'https://club.jd.com/myJdcomments/myJdcomment.action?sort=1'
               f'&page={i + 1}')
        req = requests.get(url, headers=headers)
        req_et = etree.HTML(req.text)
        Order_data.extend(req_et.xpath(
            '//*[@id="evalu01"]/div[2]/div[1]/div[@class="comt-plist"]/div[1]'))
    print(f"当前共有{N['待晒单']}个需要晒单。")
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('ul/li[1]/div/div[2]/div[1]/a/text()')[0]
        pid = Order.xpath('@pid')[0]
        oid = Order.xpath('@oid')[0]

        print(f'\t开始晒单{i},{oname}')
        # 获取图片
        url1 = (f'https://club.jd.com/discussion/getProductPageImageCommentList'
                f'.action?productId={pid}')
        imgdata = requests.get(url1, headers=headers).json()
        if imgdata["imgComments"]["imgCommentCount"] == 0:
            url1 = ('https://club.jd.com/discussion/getProductPageImage'
                    'CommentList.action?productId=1190881')
            imgdata = requests.get(url1, headers=headers).json()
        imgurl = imgdata["imgComments"]["imgList"][0]["imageUrl"]

        #
        print(f'\t\t图片url={imgurl}')
        # 提交晒单
        url2 = "https://club.jd.com/myJdcomments/saveShowOrder.action"
        headers['Referer'] = ('https://club.jd.com/myJdcomments/myJdcomment.'
                              'action?sort=1')
        headers['Origin'] = 'https://club.jd.com'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = {
            'orderId': oid,
            'productId': pid,
            'imgs': imgurl,
            'saveStatus': 3
        }
        if not opts.get('dry_run'):
            req_url2 = requests.post(url2, data={
                'orderId': oid,
                'productId': pid,
                'imgs': imgurl,
                'saveStatus': 3
            }, headers=headers)
        print('完成')
        time.sleep(SUNBW_SLEEP_SEC)
        N['待晒单'] -= 1
    return N


# 追评
def review(N, opts=None):
    opts = opts or {}
    req_et = []
    Order_data = []
    for i in range((N['待追评'] // 20) + 1):
        url = (f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=3"
               f"&page={i + 1}")
        req = requests.get(url, headers=headers)
        req_et.append(etree.HTML(req.text))
    for i in req_et:
        Order_data.extend(
            i.xpath('//*[@id="main"]/div[2]/div[2]/table/tr[@class="tr-bd"]'))
    if len(Order_data) != N['待追评']:
        for i in req_et:
            Order_data.extend(i.xpath(
                '//*[@id="main"]/div[2]/div[2]/table/tbody/tr[@class="tr-bd"]'))
    print(f"当前共有{N['待追评']}个需要追评。")
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('td[1]/div/div[2]/div/a/text()')[0]
        _id = Order.xpath('td[3]/div/a/@href')[0]
        print(f'\t开始第{i}，{oname}')
        url1 = ("https://club.jd.com/afterComments/"
                "saveAfterCommentAndShowOrder.action")
        pid, oid = _id.replace(
            'http://club.jd.com/afterComments/productPublish.action?sku=',
            "").split('&orderId=')
        _, context = generation(oname, _type=0, opts=opts)
        print(f'\t\t追评内容：{context}')
        if not opts.get('dry_run'):
            req_url1 = requests.post(url1, headers=headers, data={
                'orderId': oid,
                'productId': pid,
                'content': bytes(context, encoding="gbk"),
                'anonymousFlag': 1,
                'score': 5
            })
        print('完成')
        time.sleep(REVIEW_SLEEP_SEC)
        N['待追评'] -= 1
    return N


# 服务评价
def Service_rating(N, opts=None):
    opts = opts or {}
    Order_data = []
    req_et = []
    for i in range((N['服务评价'] // 20) + 1):
        url = (f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=4"
               f"&page={i + 1}")
        req = requests.get(url, headers=headers)
        req_et.append(etree.HTML(req.text))
    for i in req_et:
        Order_data.extend(i.xpath(
            '//*[@id="main"]/div[2]/div[2]/table/tbody/tr[@class="tr-bd"]'))
    if len(Order_data) != N['服务评价']:
        Order_data = []
        for i in req_et:
            Order_data.extend(i.xpath(
                '//*[@id="main"]/div[2]/div[2]/table/tr[@class="tr-bd"]'))
    print(f"当前共有{N['服务评价']}个需要服务评价。")
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('td[1]/div[1]/div[2]/div/a/text()')[0]
        oid = Order.xpath('td[4]/div/a[1]/@oid')[0]
        print(f'\t开始第{i}，{oname}')
        url1 = (f'https://club.jd.com/myJdcomments/insertRestSurvey.action'
                f'?voteid=145&ruleid={oid}')
        data1 = {
            'oid': oid,
            'gid': '32',
            'sid': '186194',
            'stid': '0',
            'tags': '',
            'ro591': f'591A{random.randint(4, 5)}',  # 商品符合度
            'ro592': f'592A{random.randint(4, 5)}',  # 店家服务态度
            'ro593': f'593A{random.randint(4, 5)}',  # 快递配送速度
            'ro899': f'899A{random.randint(4, 5)}',  # 快递员服务
            'ro900': f'900A{random.randint(4, 5)}'  # 快递员服务
        }
        if not opts.get('dry_run'):
            pj1 = requests.post(url1, headers=headers, data=data1)
        print("\t\t", pj1.text)
        time.sleep(SERVICE_RATING_SLEEP_SEC)
        N['服务评价'] -= 1
    return N


def No(opts=None):
    opts = opts or {}
    print()
    N = all_evaluate(opts)
    for i in N:
        print(i, N[i], end="----")
    print()
    return N


def main(opts=None):
    opts = opts or {}
    print("开始京东批量评价！")
    N = No(opts)
    if not N:
        print('Ck出现错误，请重新抓取！')
        exit()
    if N['待评价订单'] != 0:
        print("1.开始普通评价")
        N = ordinary(N, opts)
        N = No(opts)
    if N['待晒单'] != 0:
        print("2.开始晒单评价")
        N = sunbw(N, opts)
        N = No(opts)
    if N['待追评'] != 0:
        print("3.开始批量追评！")
        N = review(N, opts)
        N = No(opts)
    if N['服务评价'] != 0:
        print('4.开始服务评价')
        N = Service_rating(N, opts)
        N = No(opts)
    print("全部完成啦！")
    for i in N:
        if N[i] != 0:
            print("出现了二次错误，跳过了部分，重新尝试")
            main(opts)


if __name__ == '__main__':
    try:
        main(opts)
    except RecursionError:
        print("多次出现未完成情况，程序自动退出")
