# -*- coding: utf-8 -*-
# @Time : 2022/2/8 20:50
# @Author : @qiu-lzsnmb and @Dimlitter
# @File : auto_comment_plus.py

import argparse, uuid
import copy
import logging
import os
import random
import sys
import time
import urllib

import jieba  # just for linting
import jieba.analyse
import requests
import yaml
from lxml import etree

import jdspider

# from http2_adapter import Http2Adapter

# 常量定义
CONFIG_PATH = "./config.yml"
USER_CONFIG_PATH = "./config.user.yml"
ORDINARY_SLEEP_SEC = 10
SUNBW_SLEEP_SEC = 5
REVIEW_SLEEP_SEC = 10
SERVICE_RATING_SLEEP_SEC = 15

# 默认评价模板
DEFAULT_COMMENTS = [
    "考虑买这个$之前我是有担心过的，因为我不知道$的质量和品质怎么样，但是看了评论后我就放心了。",
    "买这个$之前我是有看过好几家店，最后看到这家店的评价不错就决定在这家店买 ",
    "看了好几家店，也对比了好几家店，最后发现还是这一家的$评价最好。",
    "看来看去最后还是选择了这家。",
    "之前在这家店也买过其他东西，感觉不错，这次又来啦。",
    "这家的$的真是太好用了，用了第一次就还想再用一次。",
    "收到货后我非常的开心，因为$的质量和品质真的非常的好！",
    "拆开包装后惊艳到我了，这就是我想要的$!",
    "快递超快！包装的很好！！很喜欢！！！",
    "包装的很精美！$的质量和品质非常不错！",
    "收到快递后迫不及待的拆了包装。$我真的是非常喜欢",
    "真是一次难忘的购物，这辈子没见过这么好用的东西！！",
    "经过了这次愉快的购物，我决定如果下次我还要买$的话，我一定会再来这家店买的。",
    "不错不错！",
    "我会推荐想买$的朋友也来这家店里买",
    "真是一次愉快的购物！",
    "大大的好评!以后买$再来你们店！(￣▽￣)",
]

# 赠品评价模板
GIFT_COMMENTS = [
    "赠品挺好的。",
    "很贴心，能有这样免费赠送的赠品!",
    "正好想着要不要多买一份增值服务，没想到还有这样的赠品。",
    "赠品正合我意。",
    "赠品很好，挺不错的。",
    "本来买了产品以后还有些担心。但是看到赠品以后就放心了。",
    "不论品质如何，至少说明店家对客的态度很好！",
    "我很喜欢这些商品！",
    "我对于商品的附加值很在乎，恰好这些赠品为这件商品提供了这样的的附加值，这令我很满意。",
    "感觉现在的网购环境环境越来越好了，以前网购的时候还没有过么多贴心的赠品和增值服务",
    "第一次用京东，被这种赠品和增值服物的良好态度感动到了。",
    "赠品还行。",
]

# logging with styles
# Reference: https://stackoverflow.com/a/384125/12002560
_COLORS = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
}

_RESET_SEQ = "\033[0m"
_COLOR_SEQ = "\033[1;%dm"
_BOLD_SEQ = "\033[1m"
_ITALIC_SEQ = "\033[3m"
_UNDERLINED_SEQ = "\033[4m"

_FORMATTER_COLORS = {
    "DEBUG": _COLORS["blue"],
    "INFO": _COLORS["green"],
    "WARNING": _COLORS["yellow"],
    "ERROR": _COLORS["red"],
    "CRITICAL": _COLORS["red"],
}


def format_style_seqs(msg: str, use_style: bool = True) -> str:
    """格式化日志消息中的样式控制字符"""
    if use_style:
        msg = msg.replace("$RESET", _RESET_SEQ)
        msg = msg.replace("$BOLD", _BOLD_SEQ)
        msg = msg.replace("$ITALIC", _ITALIC_SEQ)
        msg = msg.replace("$UNDERLINED", _UNDERLINED_SEQ)
    else:
        msg = msg.replace("$RESET", "")
        msg = msg.replace("$BOLD", "")
        msg = msg.replace("$ITALIC", "")
        msg = msg.replace("$UNDERLINED", "")
    return msg


class StyleFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, use_style=True):
        logging.Formatter.__init__(self, fmt, datefmt)
        self.use_style = use_style

    def format(self, record):
        rcd = copy.copy(record)
        levelname = rcd.levelname
        if self.use_style and levelname in _FORMATTER_COLORS:
            levelname_with_color = "%s%s%s" % (
                _COLOR_SEQ % (30 + _FORMATTER_COLORS[levelname]),
                levelname,
                _RESET_SEQ,
            )
            rcd.levelname = levelname_with_color
        return logging.Formatter.format(self, rcd)


# 生成随机文件名
def generate_unique_filename():
    # 获取当前时间戳的最后5位
    timestamp = str(int(time.time()))[-5:]

    # 生成 UUID 的前5位
    unique_id = str(uuid.uuid4().int)[:5]

    # 组合生成10位的唯一文件名
    unique_filename = f"{timestamp}{unique_id}.jpg"

    return unique_filename


# 下载图片
def download_image(img_url: str, file_name: str) -> str | None:
    """下载图片到本地
    
    Args:
        img_url: 图片URL
        file_name: 保存的文件名
        
    Returns:
        文件路径，失败返回None
    """
    full_url = f"https:{img_url}"
    try:
        response = requests.get(full_url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to download image: {e}")
        return None
    
    directory = "img"
    os.makedirs(directory, exist_ok=True)
    file_path = os.path.join(directory, file_name)
    
    with open(file_path, "wb") as file:
        file.write(response.content)
    
    return file_path


# 上传图片到JD接口
def upload_image(filename: str, file_path: str, session: requests.Session, headers: dict) -> requests.Response | None:
    """上传图片到京东
    
    Args:
        filename: 文件名
        file_path: 文件路径
        session: requests会话对象
        headers: 请求头
        
    Returns:
        响应对象，失败返回None
    """
    try:
        files = {
            "name": (None, filename),
            "Filedata": (file_path, open(file_path, "rb"), "image/jpeg"),
        }
        
        response = session.post(
            "https://club.jd.com/myJdcomments/ajaxUploadImage.action",
            headers=headers,
            files=files,
            timeout=30
        )
        return response
    except requests.RequestException as e:
        print(f"Failed to upload image: {e}")
        return None
    finally:
        # 确保文件被关闭
        if 'files' in locals():
            files["Filedata"][1].close()


# 评价生成
def generation(pname: str, _class: int = 0, _type: int = 1, opts: dict | None = None) -> tuple[int, str] | str:
    """生成评价内容
    
    Args:
        pname: 商品名称
        _class: 0-返回评价, 1-返回商品名关键词
        _type: 0-追评, 1-普通评价
        opts: 配置选项
        
    Returns:
        (_class=1时) 商品名关键词
        (_class=0时) (星级, 评价内容)
    """
    opts = opts or {}
    logger = opts.get("logger")
    
    items = [pname]
    if logger:
        logger.debug("Items: %s", items)
        logger.debug("Total loop times: %d", len(items))
    
    result = []
    for item in items:
        if logger:
            logger.debug("Current item: %s", item)
        
        try:
            spider = jdspider.JDSpider(item)
            if logger:
                logger.debug("Successfully created a JDSpider instance")
        except Exception as e:
            if logger:
                logger.warning("Failed to create JDSpider: %s", e)
            result = DEFAULT_COMMENTS[:]
            break
        
        # 增加对增值服务的评价鉴别
        if any(keyword in pname for keyword in ["赠品", "非实物", "增值服务"]):
            result = GIFT_COMMENTS[:]
        else:
            try:
                result = spider.get_data(2, 3)
            except Exception as e:
                if logger:
                    logger.warning("Failed to get data from spider: %s, using default comments", e)
                result = DEFAULT_COMMENTS[:]
        
        if logger:
            logger.debug("Result: %s", result)

    # 提取商品名关键词
    try:
        name = jieba.analyse.textrank(pname, topK=5, allowPOS="n")[0]
        if logger:
            logger.debug("Name: %s", name)
    except Exception as e:
        if logger:
            logger.warning('jieba textrank analysis error: %s, name fallback to "宝贝"', e)
        name = "宝贝"
    
    if _class == 1:
        if logger:
            logger.debug("_class is 1. Directly return name")
        return name
    
    # 生成评价内容
    num = 6 if _type == 1 else 4
    num = min(num, len(result))
    comments = "".join(random.sample(result, num))
    
    if logger:
        logger.debug("_type: %d", _type)
        logger.debug("num: %d", num)
        logger.debug("Raw comments: %s", comments)

    return 5, comments.replace("$", name)


# 查询全部评价
def all_evaluate(opts: dict | None = None) -> dict[str, int]:
    """查询各类评价数量
    
    Args:
        opts: 配置选项
        
    Returns:
        评价类型和数量的字典
    """
    opts = opts or {}
    logger = opts.get("logger")
    N = {}
    
    url = "https://club.jd.com/myJdcomments/myJdcomment.action?"
    if logger:
        logger.info("URL: %s", url)
        logger.debug("Fetching website data")
    
    try:
        req = requests.get(url, headers=headers, timeout=30)
        req.raise_for_status()
        if logger:
            logger.debug("Successfully accepted the response with status code %d", req.status_code)
    except requests.RequestException as e:
        if logger:
            logger.error("Failed to fetch evaluate data: %s", e)
        return N
    
    try:
        req_et = etree.HTML(req.text)
        if logger:
            logger.debug("Successfully parsed an XML tree")
        
        evaluate_data = req_et.xpath('//*[@id="main"]/div[2]/div[1]/div/ul/li')
        if logger:
            logger.debug("Total loop times: %d", len(evaluate_data))
        
        for ev in evaluate_data:
            na = ev.xpath("a/text()")[0]
            if logger:
                logger.debug("na: %s", na)
            try:
                num = ev.xpath("b/text()")[0]
                if logger:
                    logger.debug("num: %s", num)
            except IndexError:
                if logger:
                    logger.info("Can't find num content in XPath, fallback to 0")
                num = 0
            N[na] = int(num)
    except Exception as e:
        if logger:
            logger.error("Error parsing evaluate data: %s", e)
    
    return N


def delete_jpg() -> None:
    """删除当前目录下的所有jpg图片"""
    current_directory = os.getcwd()
    try:
        files = os.listdir(current_directory)
        for file in files:
            if file.lower().endswith(".jpg"):
                file_path = os.path.join(current_directory, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
    except OSError as e:
        print(f"Error deleting jpg files: {e}")


# 普通评价
def ordinary(N: dict[str, int], opts: dict | None = None) -> dict[str, int]:
    """处理普通评价
    
    Args:
        N: 评价数量统计
        opts: 配置选项
        
    Returns:
        更新后的评价数量统计
    """
    time.sleep(3)
    opts = opts or {}
    logger = opts.get("logger")
    
    Order_data = []
    req_et_list = []
    imgCommentCount_bool = True
    loop_times = N.get("待评价订单", 0) // 20
    
    if logger:
        logger.debug("Fetching website data")
        logger.debug("Total loop times: %d", loop_times)
    
    # 获取所有订单页面
    for i in range(loop_times + 1):
        url = f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=0&page={i + 1}"
        if logger:
            logger.debug("URL: %s", url)
        
        try:
            req = requests.get(url, headers=headers, timeout=30)
            req.raise_for_status()
            if logger:
                logger.debug("Successfully accepted the response with status code %d", req.status_code)
        except requests.RequestException as e:
            if logger:
                logger.warning("Failed to fetch page %d: %s", i + 1, e)
            continue
        
        req_et_list.append(etree.HTML(req.text))
        if logger:
            logger.debug("Successfully parsed an XML tree")
    
    # 提取订单数据
    if logger:
        logger.debug("Fetching data from XML trees")
        logger.debug("Total loop times: %d", len(req_et_list))
    
    for idx, html_tree in enumerate(req_et_list):
        if logger:
            logger.debug("Loop: %d / %d", idx + 1, len(req_et_list))
            logger.debug("Fetching order data in the default XPath")
        
        elems = html_tree.xpath('//*[@id="main"]/div[2]/div[2]/table/tbody')
        if logger:
            logger.debug("Count of fetched order data: %d", len(elems))
        Order_data.extend(elems)
    
    # 如果第一次提取失败，尝试备用XPath
    if len(Order_data) != N.get("待评价订单", 0):
        if logger:
            logger.debug('Count of fetched order data doesn\'t equal N["待评价订单"]')
            logger.debug("Clear the list Order_data")
        Order_data = []
        
        if logger:
            logger.debug("Total loop times: %d", len(req_et_list))
        
        for idx, html_tree in enumerate(req_et_list):
            if logger:
                logger.debug("Loop: %d / %d", idx + 1, len(req_et_list))
                logger.debug("Fetching order data in another XPath")
            
            elems = html_tree.xpath('//*[@id="main"]/div[2]/div[2]/table')
            if logger:
                logger.debug("Count of fetched order data: %d", len(elems))
            Order_data.extend(elems)

    if logger:
        logger.info(f"当前共有{N.get('待评价订单', 0)}个评价。")
        logger.debug("Commenting on items")
    
    # 处理每个订单
    for i, Order in enumerate(Order_data):
        try:
            oid = Order.xpath('tr[@class="tr-th"]/td/span[3]/a/text()')[0]
            oname_data = Order.xpath('tr[@class="tr-bd"]/td[1]/div[1]/div[2]/div/a/text()')
            pid_data = Order.xpath('tr[@class="tr-bd"]/td[1]/div[1]/div[2]/div/a/@href')
            
            if logger:
                logger.debug("oid: %s", oid)
                logger.debug("oname_data: %s", oname_data)
                logger.debug("pid_data: %s", pid_data)
        except IndexError:
            if logger:
                logger.warning(f"第{i + 1}个订单未查找到商品，跳过。")
            continue
        
        loop_times1 = min(len(oname_data), len(pid_data))
        if logger:
            logger.debug("Commenting on orders")
            logger.debug("Total loop times: %d", loop_times1)
        
        for idx, (oname, pid) in enumerate(zip(oname_data, pid_data)):
            if logger:
                logger.debug("Loop: %d / %d", idx + 1, loop_times1)
            
            pid = pid.replace("//item.jd.com/", "").replace(".html", "")
            if logger:
                logger.debug("pid: %s", pid)
            
            if "javascript" in pid:
                if logger:
                    logger.error(
                        "pid_data: %s,这个订单估计是京东外卖的，会导致此次评价失败，请把该 %s 商品手工评价后再运行程序。",
                        pid, oname
                    )
                continue
            
            if logger:
                logger.info(f"\t{i}.开始评价订单\t{oname}[{oid}]并晒图")
            
            # 生成评价内容
            xing, Str = generation(oname, opts=opts)
            if logger:
                logger.info(f"\t\t评价内容,星级{xing}：" + Str)
            
            # 获取图片
            if logger:
                logger.info(f"\t\t开始获取图片")
            
            img_url = f"https://club.jd.com/discussion/getProductPageImageCommentList.action?productId={pid}"
            if logger:
                logger.debug("URL: %s", img_url)
            
            try:
                img_resp = requests.get(img_url, headers=headers, timeout=30)
                img_resp.raise_for_status()
                if logger:
                    logger.debug("Successfully accepted the response with status code %d", img_resp.status_code)
            except requests.RequestException as e:
                if logger:
                    logger.warning("Failed to fetch images: %s", e)
                imgCommentCount_bool = False
                imgurl = ""
            else:
                if logger:
                    logger.info("imgdata_url:" + img_url)
                
                imgdata = img_resp.json()
                if logger:
                    logger.debug("Image data: %s", imgdata)
                
                if imgdata["imgComments"]["imgCommentCount"] == 0:
                    if logger:
                        logger.warning("这单没有图片数据，所以直接默认五星好评！！")
                    imgCommentCount_bool = False
                    imgurl = ""
                elif imgdata["imgComments"]["imgCommentCount"] > 0:
                    imgurl1 = imgdata["imgComments"]["imgList"][0]["imageUrl"]
                    imgurl2 = imgdata["imgComments"]["imgList"][1]["imageUrl"]
                    
                    if logger:
                        logger.info("imgurl1 url: %s", imgurl1)
                        logger.info("imgurl2 url: %s", imgurl2)
                    
                    session = requests.Session()
                    imgBasic = "//img20.360buyimg.com/shaidan/s645x515_"
                    
                    # 下载并上传第一张图片
                    imgName1 = generate_unique_filename()
                    if logger:
                        logger.debug(f"Image :{imgName1}")
                    
                    downloaded_file1 = download_image(imgurl1, imgName1)
                    if downloaded_file1:
                        imgPart1 = upload_image(imgName1, downloaded_file1, session, headers)
                        if imgPart1 and imgPart1.status_code == 200 and ".jpg" in imgPart1.text:
                            imgurl1t = f"{imgBasic}{imgPart1.text}"
                        else:
                            if logger:
                                logger.info("上传图片1失败")
                            imgurl1 = ""
                    
                    # 下载并上传第二张图片
                    imgName2 = generate_unique_filename()
                    if logger:
                        logger.debug(f"Image :{imgName2}")
                    
                    downloaded_file2 = download_image(imgurl2, imgName2)
                    if downloaded_file2:
                        imgPart2 = upload_image(imgName2, downloaded_file2, session, headers)
                        if imgPart2 and imgPart2.status_code == 200 and ".jpg" in imgPart2.text:
                            imgurl2t = f"{imgBasic}{imgPart2.text}"
                        else:
                            if logger:
                                logger.info("上传图片2失败")
                            imgurl2 = ""
                    
                    imgurl = f"{imgurl1},{imgurl2}"
                    if logger:
                        logger.debug("Image URL: %s", imgurl)
                        logger.info(f"\t\t图片url={imgurl}")
                else:
                    imgurl = ""
            
            # 准备评价数据
            Str_encoded = urllib.parse.quote(Str, safe="/", encoding=None, errors=None)
            Comment_data = {
                "orderId": oid,
                "productId": pid,
                "score": str(xing),
                "content": Str_encoded,
                "saveStatus": "1",
                "anonymousFlag": "1",
            }
            
            if imgCommentCount_bool and imgurl:
                Comment_data["imgs"] = imgurl
            
            if logger:
                logger.debug("Data: %s", Comment_data)
            
            # 发送评价请求
            if not opts.get("dry_run"):
                if logger:
                    logger.debug("Sending comment request")
                
                try:
                    Comment_resp = requests.post(
                        "https://club.jd.com/myJdcomments/saveProductComment.action",
                        headers=headers2,
                        data=Comment_data,
                        timeout=30
                    )
                    if logger:
                        logger.info(
                            "发送请求后的状态码:{},text:{}".format(
                                Comment_resp.status_code, Comment_resp.text
                            )
                        )
                    
                    if Comment_resp.status_code == 200 and Comment_resp.json().get("success"):
                        if logger:
                            logger.info(f"\t{i}.评价订单\t{oname}[{oid}]评论成功")
                    else:
                        if logger:
                            logger.warning(f"\t{i}.评价订单\t{oname}[{oid}]评论失败")
                except requests.RequestException as e:
                    if logger:
                        logger.error(f"Failed to submit comment: {e}")
                except (ValueError, KeyError) as e:
                    if logger:
                        logger.error(f"Failed to parse response: {e}")
            else:
                if logger:
                    logger.debug("Skipped sending comment request in dry run")
            
            if logger:
                logger.debug("Sleep time (s): %.1f", ORDINARY_SLEEP_SEC)
            time.sleep(ORDINARY_SLEEP_SEC)
    
    N["待评价订单"] = max(0, N.get("待评价订单", 0) - 1)
    return N


"""
# 晒单评价
def sunbw(N, opts=None):
    opts = opts or {}
    Order_data = []
    loop_times = N['待晒单'] // 20
    opts['logger'].debug('Fetching website data')
    opts['logger'].debug('Total loop times: %d', loop_times)
    for i in range(loop_times + 1):
        opts['logger'].debug('Loop: %d / %d', i + 1, loop_times)
        url = (f'https://club.jd.com/myJdcomments/myJdcomment.action?sort=1'
               f'&page={i + 1}')
        opts['logger'].debug('URL: %s', url)
        req = requests.get(url, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req.status_code)
        req_et = etree.HTML(req.text)
        opts['logger'].debug('Successfully parsed an XML tree')
        opts['logger'].debug('Fetching data from XML trees')
        elems = req_et.xpath(
            '//*[@id="evalu01"]/div[2]/div[1]/div[@class="comt-plist"]/div[1]')
        opts['logger'].debug('Count of fetched order data: %d', len(elems))
        Order_data.extend(elems)
    opts['logger'].info(f"当前共有{N['待晒单']}个需要晒单。")
    opts['logger'].debug('Commenting on items')
    for i, Order in enumerate(Order_data):
        oname = Order.xpath('ul/li[1]/div/div[2]/div[1]/a/text()')[0]
        pid = Order.xpath('@pid')[0]
        oid = Order.xpath('@oid')[0]
        opts['logger'].info(f'\t开始第{i+1}，{oname}')
        opts['logger'].debug('pid: %s', pid)
        opts['logger'].debug('oid: %s', oid)
        # 获取图片
        url1 = (f'https://club.jd.com/discussion/getProductPageImageCommentList'
                f'.action?productId={pid}')
        opts['logger'].debug('Fetching images using the default URL')
        opts['logger'].debug('URL: %s', url1)
        req1 = requests.get(url1, headers=headers)
        opts['logger'].debug(
            'Successfully accepted the response with status code %d',
            req1.status_code)
        if not req.ok:
            opts['logger'].warning(
                'Status code of the response is %d, not 200', req1.status_code)
        imgdata = req1.json()
        opts['logger'].debug('Image data: %s', imgdata)
        if imgdata["imgComments"]["imgCommentCount"] == 0:
            opts['logger'].debug('Count of fetched image comments is 0')
            opts['logger'].debug('Fetching images using another URL')
            url1 = ('https://club.jd.com/discussion/getProductPageImage'
                    'CommentList.action?productId=1190881')
            opts['logger'].debug('URL: %s', url1)
            req1 = requests.get(url1, headers=headers)
            opts['logger'].debug(
                'Successfully accepted the response with status code %d',
                req1.status_code)
            if not req.ok:
                opts['logger'].warning(
                    'Status code of the response is %d, not 200',
                    req1.status_code)
            imgdata = req1.json()
            opts['logger'].debug('Image data: %s', imgdata)
        imgurl = imgdata["imgComments"]["imgList"][0]["imageUrl"]
        opts['logger'].debug('Image URL: %s', imgurl)

        opts['logger'].info(f'\t\t图片url={imgurl}')
        # 提交晒单
        opts['logger'].debug('Preparing for commenting')
        url2 = "https://club.jd.com/myJdcomments/saveShowOrder.action"
        opts['logger'].debug('URL: %s', url2)
        headers['Referer'] = ('https://club.jd.com/myJdcomments/myJdcomment.'
                              'action?sort=1')
        headers['Origin'] = 'https://club.jd.com'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        opts['logger'].debug('New header for this request: %s', headers)
        data = {
            'orderId': oid,
            'productId': pid,
            'imgs': imgurl,
            'saveStatus': 3
        }
        opts['logger'].debug('Data: %s', data)
        if not opts.get('dry_run'):
            opts['logger'].debug('Sending comment request')
            req_url2 = requests.post(url2, data=data, headers=headers)
        else:
            opts['logger'].debug('Skipped sending comment request in dry run')
        opts['logger'].info('完成')
        opts['logger'].debug('Sleep time (s): %.1f', SUNBW_SLEEP_SEC)
        time.sleep(SUNBW_SLEEP_SEC)
        N['待晒单'] -= 1
    return N
"""

# 追评
def review(N: dict[str, int], opts: dict | None = None) -> dict[str, int]:
    """处理追评
    
    Args:
        N: 评价数量统计
        opts: 配置选项
        
    Returns:
        更新后的评价数量统计
    """
    opts = opts or {}
    logger = opts.get("logger")
    
    req_et_list = []
    Order_data = []
    loop_times = N.get("待追评", 0) // 20
    
    if logger:
        logger.debug("Fetching website data")
        logger.debug("Total loop times: %d", loop_times)
    
    # 获取所有页面
    for i in range(loop_times + 1):
        if logger:
            logger.debug("Loop: %d / %d", i + 1, loop_times)
        
        url = f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=3&page={i + 1}"
        if logger:
            logger.debug("URL: %s", url)
        
        try:
            req = requests.get(url, headers=headers, timeout=30)
            req.raise_for_status()
            if logger:
                logger.debug("Successfully accepted the response with status code %d", req.status_code)
        except requests.RequestException as e:
            if logger:
                logger.warning("Failed to fetch page %d: %s", i + 1, e)
            continue
        
        req_et_list.append(etree.HTML(req.text))
        if logger:
            logger.debug("Successfully parsed an XML tree")
    
    # 提取订单数据
    if logger:
        logger.debug("Fetching data from XML trees")
        logger.debug("Total loop times: %d", len(req_et_list))
    
    for idx, html_tree in enumerate(req_et_list):
        if logger:
            logger.debug("Loop: %d / %d", idx + 1, len(req_et_list))
            logger.debug("Fetching order data in the default XPath")
        
        elems = html_tree.xpath('//*[@id="main"]/div[2]/div[2]/table/tr[@class="tr-bd"]')
        if logger:
            logger.debug("Count of fetched order data: %d", len(elems))
        Order_data.extend(elems)
    
    # 如果第一次提取失败，尝试备用XPath
    if len(Order_data) != N.get("待追评", 0):
        if logger:
            logger.debug('Count of fetched order data doesn\'t equal N["待追评"]')
        
        if logger:
            logger.debug("Total loop times: %d", len(req_et_list))
        
        for idx, html_tree in enumerate(req_et_list):
            if logger:
                logger.debug("Loop: %d / %d", idx + 1, len(req_et_list))
                logger.debug("Fetching order data in another XPath")
            
            elems = html_tree.xpath('//*[@id="main"]/div[2]/div[2]/table/tbody/tr[@class="tr-bd"]')
            if logger:
                logger.debug("Count of fetched order data: %d", len(elems))
            Order_data.extend(elems)
    
    if logger:
        logger.info(f"当前共有 {N.get('待追评', 0)} 个需要追评。")
        logger.debug("Commenting on items")
    
    # 处理每个订单
    for i, Order in enumerate(Order_data):
        try:
            oname = Order.xpath("td[1]/div/div[2]/div/a/text()")[0]
            _id = Order.xpath("td[3]/div/a/@href")[0]
        except IndexError as e:
            if logger:
                logger.warning(f"Failed to extract order info for item {i+1}: {e}")
            continue
        
        if logger:
            logger.info(f"\t开始追评第{i+1}，{oname}")
            logger.debug("_id: %s", _id)
        
        url1 = "https://club.jd.com/afterComments/saveAfterCommentAndShowOrder.action"
        if logger:
            logger.debug("URL: %s", url1)
        
        try:
            pid, oid = _id.replace(
                "http://club.jd.com/afterComments/productPublish.action?sku=", ""
            ).split("&orderId=")
        except ValueError as e:
            if logger:
                logger.error(f"Failed to parse product ID and order ID: {e}")
            continue
        
        if logger:
            logger.debug("pid: %s", pid)
            logger.debug("oid: %s", oid)
        
        if "javascript" in pid:
            if logger:
                logger.error(
                    "pid_data: %s,这个订单估计是京东外卖的，会导致此次评价失败，请把该 %s 商品手工评价后再运行程序。",
                    pid, oname
                )
            continue
        
        # 生成追评内容
        _, context = generation(oname, _type=0, opts=opts)
        if logger:
            logger.info(f"\t\t追评内容：{context}")
        
        context_encoded = urllib.parse.quote(context, safe="/", encoding=None, errors=None)
        data1 = {
            "orderId": oid,
            "productId": pid,
            "content": context_encoded,
            "anonymousFlag": 1,
            "score": 5,
            "imgs": "",
        }
        
        if logger:
            logger.debug("Data: %s", data1)
        
        # 发送追评请求
        if not opts.get("dry_run"):
            if logger:
                logger.debug("Sending comment request")
            
            try:
                pj1 = requests.post(url1, headers=headers2, data=data1, timeout=30)
                if logger:
                    logger.debug("发送请求后的状态码:{},text:{}".format(pj1.status_code, pj1.text))
            except requests.RequestException as e:
                if logger:
                    logger.error(f"Failed to submit review: {e}")
        else:
            if logger:
                logger.debug("Skipped sending comment request in dry run")
        
        if logger:
            logger.info("完成")
            logger.debug("Sleep time (s): %.1f", REVIEW_SLEEP_SEC)
        
        time.sleep(REVIEW_SLEEP_SEC)
        N["待追评"] = max(0, N.get("待追评", 0) - 1)
    
    return N


# 服务评价
def Service_rating(N: dict[str, int], opts: dict | None = None) -> dict[str, int]:
    """处理服务评价
    
    Args:
        N: 评价数量统计
        opts: 配置选项
        
    Returns:
        更新后的评价数量统计
    """
    opts = opts or {}
    logger = opts.get("logger")
    
    Order_data = []
    req_et_list = []
    loop_times = N.get("服务评价", 0) // 20
    
    if logger:
        logger.debug("Fetching website data")
        logger.debug("Total loop times: %d", loop_times)
    
    # 获取所有页面
    for i in range(loop_times + 1):
        if logger:
            logger.debug("Loop: %d / %d", i + 1, loop_times)
        
        url = f"https://club.jd.com/myJdcomments/myJdcomment.action?sort=4&page={i + 1}"
        if logger:
            logger.debug("URL: %s", url)
        
        try:
            req = requests.get(url, headers=headers, timeout=30)
            req.raise_for_status()
            if logger:
                logger.debug("Successfully accepted the response with status code %d", req.status_code)
        except requests.RequestException as e:
            if logger:
                logger.warning("Failed to fetch page %d: %s", i + 1, e)
            continue
        
        req_et_list.append(etree.HTML(req.text))
        if logger:
            logger.debug("Successfully parsed an XML tree")
    
    # 提取订单数据
    if logger:
        logger.debug("Fetching data from XML trees")
        logger.debug("Total loop times: %d", len(req_et_list))
    
    for idx, html_tree in enumerate(req_et_list):
        if logger:
            logger.debug("Loop: %d / %d", idx + 1, len(req_et_list))
            logger.debug("Fetching order data in the default XPath")
        
        elems = html_tree.xpath('//*[@id="main"]/div[2]/div[2]/table/tbody/tr[@class="tr-bd"]')
        if logger:
            logger.debug("Count of fetched order data: %d", len(elems))
        Order_data.extend(elems)
    
    # 如果第一次提取失败，尝试备用XPath
    if len(Order_data) != N.get("服务评价", 0):
        if logger:
            logger.debug('Count of fetched order data doesn\'t equal N["服务评价"]')
            logger.debug("Clear the list Order_data")
        Order_data = []
        
        if logger:
            logger.debug("Total loop times: %d", len(req_et_list))
        
        for idx, html_tree in enumerate(req_et_list):
            if logger:
                logger.debug("Loop: %d / %d", idx + 1, len(req_et_list))
                logger.debug("Fetching order data in another XPath")
            
            elems = html_tree.xpath('//*[@id="main"]/div[2]/div[2]/table/tr[@class="tr-bd"]')
            if logger:
                logger.debug("Count of fetched order data: %d", len(elems))
            Order_data.extend(elems)
    
    if logger:
        logger.info(f"当前共有{N.get('服务评价', 0)}个需要第一次服务评价。")
        logger.debug("Commenting on items")
    
    # 处理每个订单
    for i, Order in enumerate(Order_data):
        try:
            oname = Order.xpath("td[1]/div[1]/div[2]/div/a/text()")[0]
            oid = Order.xpath("td[4]/div/a[1]/@oid")[0]
        except IndexError as e:
            if logger:
                logger.warning(f"Failed to extract order info for item {i+1}: {e}")
            continue
        
        if logger:
            logger.info(f"\t开始第一次评论，{i+1}，{oname}")
            logger.debug("oid: %s", oid)
        
        url1 = f"https://club.jd.com/myJdcomments/insertRestSurvey.action?voteid=145&ruleid={oid}"
        if logger:
            logger.debug("URL: %s", url1)
        
        data1 = {
            "oid": oid,
            "gid": "32",
            "sid": "186194",
            "stid": "0",
            "tags": "",
            "ro591": f"591A{random.randint(4, 5)}",  # 商品符合度
            "ro592": f"592A{random.randint(4, 5)}",  # 店家服务态度
            "ro593": f"593A{random.randint(4, 5)}",  # 快递配送速度
            "ro899": f"899A{random.randint(4, 5)}",  # 快递员服务
            "ro900": f"900A{random.randint(4, 5)}",  # 快递员服务
        }
        
        if logger:
            logger.debug("Data: %s", data1)
        
        # 发送服务评价请求
        if not opts.get("dry_run"):
            if logger:
                logger.debug("Sending comment request")
            
            try:
                pj1 = requests.post(url1, headers=headers, data=data1, timeout=30)
                if logger:
                    logger.info("\t\t " + pj1.text)
            except requests.RequestException as e:
                if logger:
                    logger.error(f"Failed to submit service rating: {e}")
        else:
            if logger:
                logger.debug("Skipped sending comment request in dry run")
        
        if logger:
            logger.debug("Sleep time (s): %.1f", SERVICE_RATING_SLEEP_SEC)
        
        time.sleep(SERVICE_RATING_SLEEP_SEC)
        N["服务评价"] = max(0, N.get("服务评价", 0) - 1)
    
    return N


def No(opts: dict | None = None) -> dict[str, int]:
    """获取评价统计信息
    
    Args:
        opts: 配置选项
        
    Returns:
        评价数量统计字典
    """
    opts = opts or {}
    logger = opts.get("logger")
    
    N = all_evaluate(opts)
    if logger:
        s = "----".join([f"{i} {N[i]}" for i in N])
        logger.info(s)
    
    return N


def main(opts: dict | None = None) -> None:
    """主函数，执行所有评价流程
    
    Args:
        opts: 配置选项
    """
    opts = opts or {}
    logger = opts.get("logger")
    
    if logger:
        logger.info("开始京东批量评价！")
    
    N = No(opts)
    if logger:
        logger.debug("N value after executing No(): %s", N)
    
    if not N:
        if logger:
            logger.error("Ck出现错误，请重新抓取！")
        sys.exit(1)
    
    if logger:
        logger.info(f"已评价：{N.get('已评价', 0)}个")
    
    # 普通评价
    if N.get("待评价订单", 0) != 0:
        if logger:
            logger.info("1.开始普通评价")
        N = ordinary(N, opts)
        if logger:
            logger.debug("N value after executing ordinary(): %s", N)
        N = No(opts)
        if logger:
            logger.debug("N value after executing No(): %s", N)
    
    # 追评
    if N.get("待追评", 0) != 0:
        if logger:
            logger.info("3.开始批量追评,注意：追评不会自动上传图片")
        N = review(N, opts)
        if logger:
            logger.debug("N value after executing review(): %s", N)
        N = No(opts)
        if logger:
            logger.debug("N value after executing No(): %s", N)
    
    # 服务评价
    if N.get("服务评价", 0) != 0:
        if logger:
            logger.info("4.开始服务评价")
        N = Service_rating(N, opts)
        if logger:
            logger.debug("N value after executing Service_rating(): %s", N)
        N = No(opts)
        if logger:
            logger.debug("N value after executing No(): %s", N)
    
    if logger:
        logger.info("全部完成啦！")
    
    # 检查是否有未完成的评价，递归重试
    for key in N:
        if N[key] != 0:
            if logger:
                logger.warning("出现了二次错误，跳过了部分，重新尝试")
            main(opts)
            break


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="京东自动评价工具")
    parser.add_argument(
        "--dry-run",
        help="完整运行但不提交评价（测试模式）",
        action="store_true",
    )
    parser.add_argument(
        "-lv",
        "--log-level",
        help="指定日志级别 (默认: INFO)",
        default="INFO",
        choices=["DEBUG", "WARN", "INFO", "ERROR", "FATAL"],
    )
    parser.add_argument(
        "-o", "--log-file", help="指定日志文件路径", default="log.txt"
    )
    args = parser.parse_args()
    
    # 规范化日志级别
    log_level = args.log_level.upper()
    if log_level in ["WARN", "FATAL"]:
        # WARN是WARNING的别名，FATAL是CRITICAL的别名
        pass
    
    opts = {
        "dry_run": args.dry_run,
        "log_level": log_level,
        "log_file": args.log_file,
    }

    # 配置控制台日志
    _logging_level = getattr(logging, log_level if log_level != "WARN" else "WARNING")
    logger = logging.getLogger("comment")
    logger.setLevel(level=_logging_level)
    
    # 创建格式化器
    formatter = StyleFormatter("%(asctime)s %(levelname)-19s %(message)s")
    rawformatter = StyleFormatter(
        "%(asctime)s %(levelname)-8s %(message)s", use_style=False
    )
    
    # 添加控制台处理器
    console = logging.StreamHandler()
    console.setLevel(_logging_level)
    console.setFormatter(formatter)
    logger.addHandler(console)
    opts["logger"] = logger
    
    # 配置jieba日志
    jieba.default_logger = logging.getLogger("jieba")
    jieba.default_logger.setLevel(level=_logging_level)
    jieba.default_logger.addHandler(console)
    
    # 配置jdspider日志
    jdspider.default_logger = logging.getLogger("spider")
    jdspider.default_logger.setLevel(level=_logging_level)
    jdspider.default_logger.addHandler(console)

    if logger:
        logger.debug("Successfully set up console logger")
        logger.debug("CLI arguments: %s", args)
        logger.debug("Opening the log file")
    
    # 配置文件日志
    if opts["log_file"]:
        try:
            handler = logging.FileHandler(opts["log_file"], "w", encoding="utf-8")
            handler.setLevel(_logging_level)
            handler.setFormatter(rawformatter)
            logger.addHandler(handler)
            jieba.default_logger.addHandler(handler)
            jdspider.default_logger.addHandler(handler)
            if logger:
                logger.debug("Successfully set up file logger")
        except Exception as e:
            if logger:
                logger.error("Failed to open the file handler")
                logger.error("Error message: %s", e)
            sys.exit(1)
    
    if logger:
        logger.debug("Options passed to functions: %s", opts)
        logger.debug("Builtin constants:")
        logger.debug("  CONFIG_PATH: %s", CONFIG_PATH)
        logger.debug("  USER_CONFIG_PATH: %s", USER_CONFIG_PATH)
        logger.debug("  ORDINARY_SLEEP_SEC: %s", ORDINARY_SLEEP_SEC)
        logger.debug("  SUNBW_SLEEP_SEC: %s", SUNBW_SLEEP_SEC)
        logger.debug("  REVIEW_SLEEP_SEC: %s", REVIEW_SLEEP_SEC)
        logger.debug("  SERVICE_RATING_SLEEP_SEC: %s", SERVICE_RATING_SLEEP_SEC)

    # 读取配置文件
    if logger:
        logger.debug("Reading the configuration file")
    
    if os.path.exists(USER_CONFIG_PATH):
        if logger:
            logger.debug("User configuration file exists")
        _cfg_path = USER_CONFIG_PATH
    else:
        if logger:
            logger.debug("User configuration file doesn't exist, fallback to the default one")
        _cfg_path = CONFIG_PATH
    
    try:
        with open(_cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if logger:
            logger.debug("Closed the configuration file")
            logger.debug("Configurations in Python-dict format: %s", cfg)
    except Exception as e:
        if logger:
            logger.error("Failed to read configuration file: %s", e)
        sys.exit(1)
    
    # 设置Cookie
    ck = cfg["user"]["cookie"]
    jdspider.cookie = ck.encode("utf-8")

    # 定义请求头
    headers2 = {
        "Cookie": ck.encode("utf-8"),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.5735.110 Safari/537.36",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": "",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://club.jd.com/",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    
    headers = {
        "Cookie": ck.encode("utf-8"),
        "User-Agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0 Sec-Ch-Ua: "Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
        "DNT": "1",
    }
    
    if logger:
        logger.debug("Builtin HTTP request header: %s", headers)
        logger.debug("Starting main processes")
    
    # 执行主流程
    try:
        main(opts)
    except RecursionError:
        if logger:
            logger.error("多次出现未完成情况，程序自动退出")
        sys.exit(1)
