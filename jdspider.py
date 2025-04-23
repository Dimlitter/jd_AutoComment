# @Time : 2022/2/8 20:50
# @Author :@Zhang Jiale and @Dimlitter
# @File : jdspider.py

import json
import logging
import random
import re
import sys
import time
from urllib.parse import quote, urlencode

import requests
import yaml
import zhon.hanzi
from lxml import etree

# 加载配置文件
with open("./config.yml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# 获取用户的 cookie
cookie = cfg["user"]["cookie"]

# 配置日志输出到标准错误流
log_console = logging.StreamHandler(sys.stderr)
default_logger = logging.getLogger("jdspider")
default_logger.setLevel(logging.DEBUG)
default_logger.addHandler(log_console)

# 定义基础请求头，避免重复代码
BASE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,"
              "*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "max-age=0",
    "dnt": "1",
    "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="98", "Google Chrome";v="98"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/98.0.4758.82 Safari/537.36",
}

class JDSpider:
    """
    京东爬虫类，用于爬取指定商品类别的评论信息。
    传入商品类别（如手机、电脑）构造实例，然后调用 getData 方法爬取数据。
    """
    def __init__(self, categlory):
        # 京东搜索商品的起始页面 URL
        self.startUrl = "https://search.jd.com/Search?keyword=%s&enc=utf-8" % (
            quote(categlory)
        )
        # 评论接口的基础 URL
        self.commentBaseUrl = "https://api.m.jd.com/?"
        # 基础请求头
        self.headers = BASE_HEADERS.copy()
        # 带 cookie 的请求头
        self.headers2 = {
            **BASE_HEADERS,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
            "cookie": cookie,
            "priority": "u=0, i",
            "sec-ch-ua": '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-mode": "navigate",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
        }
        # 获取商品 ID 列表
        self.productsId = self.getId()
        # 评论类型映射，1 差评，2 中评，3 好评
        self.comtype = {1: "negative", 2: "medium", 3: "positive"}  # 修正拼写错误
        # 商品类别
        self.categlory = categlory
        # IP 列表，用于代理（当前为空）
        self.iplist = {"http": [], "https": []}

    def getParamUrl(self, productid: str, page: str, score: str):
        """
        生成评论接口的请求参数和完整 URL。
        :param productid: 商品 ID
        :param page: 评论页码
        :param score: 评论类型（1 差评，2 中评，3 好评）
        :return: 请求参数和完整 URL
        """
        params = {
            "appid": "item-v3",
            "functionId": "pc_club_productPageComments",
            "client": "pc",
            "body": {
                "productId": productid,
                "score": score,
                "sortType": "5",
                "page": page,
                "pageSize": "10",
                "isShadowSku": "0",
                "rid": "0",
                "fold": "1",
            },
        }
        default_logger.info("请求参数: " + str(params))
        url = self.commentBaseUrl + urlencode(params)
        default_logger.info("请求 URL: " + str(url))
        return params, url

    def getHeaders(self, productid: str) -> dict:
        """
        生成爬取指定商品评论时所需的请求头。
        :param productid: 商品 ID
        :return: 请求头字典
        """
        return {
            "Referer": f"https://item.jd.com/{productid}.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/75.0.3770.142 Safari/537.36",
            # "cookie": cookie,
        }

    def getId(self) -> list:
        """
        从京东搜索页面获取商品 ID 列表。
        :return: 商品 ID 列表
        """
        try:
            response = requests.get(self.startUrl, headers=self.headers2)
            response.raise_for_status()  # 检查响应状态码
            default_logger.info("获取同类产品的搜索 URL 结果：" + self.startUrl)
        except requests.RequestException as e:
            default_logger.warning(f"请求异常，状态码错误，爬虫连接异常！错误信息: {e}")
            return []

        html = etree.HTML(response.text)
        return html.xpath('//li[@class="gl-item"]/@data-sku')

    def getData(self, maxPage: int, score: int):
        """
        爬取指定商品类别的评论信息。
        :param maxPage: 最大爬取页数，每页 10 条评论
        :param score: 评论类型（1 差评，2 中评，3 好评）
        :return: 处理后的评论列表
        """
        comments = []
        scores = []
        default_logger.info("爬取商品数量最多为 8 个，请耐心等待，也可以自行修改 jdspider 文件")

        # 确定要爬取的商品数量
        product_count = min(len(self.productsId), 8) if self.productsId else 0
        if product_count == 0:
            default_logger.warning("self.productsId 为空，将使用默认评价")
        default_logger.info("要爬取的商品数量: " + str(product_count))

        for j in range(product_count):
            product_id = self.productsId[j]
            for i in range(1, maxPage):
                params, url = self.getParamUrl(product_id, str(i), str(score))
                default_logger.info(f"正在爬取第 {j + 1} 个商品的第 {i} 页评论信息")

                try:
                    default_logger.info(f"爬取商品评价的 URL 链接是 {url}，商品的 ID 是：{product_id}")
                    response = requests.get(url, headers=self.getHeaders(product_id))
                    response.raise_for_status()  # 检查响应状态码
                except requests.RequestException as e:
                    default_logger.warning(f"请求异常: {e}")
                    continue

                time.sleep(random.randint(5, 10))  # 设置时延，防止被封 IP

                if not response.text:
                    default_logger.warning("未爬取到信息")
                    continue

                try:
                    res_json = json.loads(response.text)
                except json.JSONDecodeError as e:
                    default_logger.warning(f"JSON 解析异常: {e}")
                    continue

                if not res_json.get("comments"):
                    default_logger.warning(f"页面次数已到：{i}，超出范围(或未爬取到评论)")
                    break

                for comment_data in res_json["comments"]:
                    comment = comment_data["content"].replace("\n", " ").replace("\r", " ")
                    comments.append(comment)
                    scores.append(comment_data["score"])

        default_logger.info(f"已爬取 {len(comments)} 条 {self.comtype[score]} 评价信息")

        # 处理评论，拆分成句子
        remarks = []
        for comment in comments:
            sentences = re.findall(zhon.hanzi.sentence, comment)
            if not sentences or sentences in [["。"], ["？"], ["！"], ["."], [","], ["?"], ["!"]]:
                default_logger.warning(f"拆分失败或结果不符(去除空格和标点符号)：{sentences}")
            else:
                remarks.append(sentences)

        result = self.solvedata(remarks=remarks)

        if not result:
            default_logger.warning("当前商品没有评价，使用默认评价")
            result = [
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
                "真是一次愉快的购物！",
            ]

        return result

    def solvedata(self, remarks) -> list:
        """
        将评论拆分成句子列表。
        :param remarks: 包含评论句子列表的列表
        :return: 所有评论句子组成的列表
        """
        sentences = []
        for item in remarks:
            for sentence in item:
                sentences.append(sentence)
        default_logger.info("爬取的评价结果：" + str(sentences))
        return sentences

# 测试用例
if __name__ == "__main__":
    jdlist = ["商品名"]
    for item in jdlist:
        spider = JDSpider(item)
        spider.getData(2, 3)
