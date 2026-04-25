# @Time : 2022/2/8 20:50
# @Author :@Zhang Jiale and @Dimlitter
# @File : jdspider.py

import json
import logging
import random
import re
import sys
import time
from typing import Any
from urllib.parse import quote

import requests
import yaml
import zhon.hanzi
from lxml import etree

# 配置日志（延迟初始化，由外部设置）
default_logger = logging.getLogger("jdspider")

# 默认评价模板（与 auto_comment_plus.py 保持一致）
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

# Cookie（由外部设置）
cookie: bytes = b""

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

    # 常量定义
    MAX_PRODUCTS = 8  # 最大爬取商品数量
    REQUEST_TIMEOUT = 30  # 请求超时时间（秒）
    MIN_DELAY = 5  # 最小延迟时间（秒）
    MAX_DELAY = 10  # 最大延迟时间（秒）

    def __init__(self, category: str):
        """
        初始化京东爬虫
        
        Args:
            category: 商品类别（如手机、电脑）
        """
        if not category or not category.strip():
            raise ValueError("商品类别不能为空")
        
        # 京东搜索商品的起始页面 URL
        self.start_url = f"https://search.jd.com/Search?keyword={quote(category)}&enc=utf-8"
        # 评论接口的基础 URL
        self.comment_base_url = "https://club.jd.com"
        # 基础请求头
        self.headers = BASE_HEADERS.copy()
        # 带 cookie 的请求头
        self.headers_with_cookie = {
            **BASE_HEADERS,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
            "Cookie": cookie.decode("utf-8") if isinstance(cookie, bytes) else cookie,
            "priority": "u=0, i",
            "sec-ch-ua": '"Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-mode": "navigate",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
        }
        # 评论类型映射，1 差评，2 中评，3 好评
        self.comment_types = {1: "negative", 2: "medium", 3: "positive"}
        # 商品类别
        self.category = category
        # 获取商品 ID 列表
        self.product_ids = self._get_product_ids()

    def _build_comment_url(self, product_id: str, page: int, score: int) -> str:
        """
        构建评论接口的完整 URL
        
        Args:
            product_id: 商品 ID
            page: 评论页码
            score: 评论类型（1 差评，2 中评，3 好评）
            
        Returns:
            完整的评论接口 URL
        """
        path = f"/discussion/getProductPageImageCommentList.action?productId={product_id}"
        url = self.comment_base_url + path
        
        if default_logger:
            default_logger.debug("评论接口 URL: %s", url)
        
        return url

    def _get_request_headers(self, product_id: str) -> dict[str, str]:
        """
        生成爬取指定商品评论时所需的请求头
        
        Args:
            product_id: 商品 ID
            
        Returns:
            请求头字典
        """
        return {
            "Referer": f"https://item.jd.com/{product_id}.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/75.0.3770.142 Safari/537.36",
        }

    def _get_product_ids(self) -> list[str]:
        """
        从京东搜索页面获取商品 ID 列表
        
        Returns:
            商品 ID 列表
        """
        try:
            if default_logger:
                default_logger.info("正在搜索商品: %s", self.category)
                default_logger.debug("搜索 URL: %s", self.start_url)
            
            response = requests.get(
                self.start_url, 
                headers=self.headers_with_cookie,
                timeout=self.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            if default_logger:
                default_logger.info("成功获取搜索结果")
        except requests.RequestException as e:
            if default_logger:
                default_logger.warning("请求异常，爬虫连接失败: %s", e)
            return []
        except Exception as e:
            if default_logger:
                default_logger.error("未知错误: %s", e)
            return []

        try:
            html = etree.HTML(response.text)
            product_ids = html.xpath('//li[@class="gl-item"]/@data-sku')
            
            if default_logger:
                default_logger.info("找到 %d 个相关商品", len(product_ids))
            
            return product_ids
        except Exception as e:
            if default_logger:
                default_logger.error("解析HTML失败: %s", e)
            return []

    def get_data(self, max_page: int = 2, score: int = 3) -> list[str]:
        """
        爬取指定商品类别的评论信息
        
        Args:
            max_page: 最大爬取页数，每页约10条评论（默认2页）
            score: 评论类型（1=差评, 2=中评, 3=好评，默认3好评）
            
        Returns:
            处理后的评论句子列表
        """
        if score not in self.comment_types:
            raise ValueError(f"无效的评论类型: {score}，必须是 1(差评)、2(中评) 或 3(好评)")
        
        comments = []
        
        if default_logger:
            default_logger.info(
                "开始爬取评论 - 商品: %s, 类型: %s, 最多爬取 %d 个商品, %d 页",
                self.category,
                self.comment_types[score],
                self.MAX_PRODUCTS,
                max_page
            )

        # 确定要爬取的商品数量
        product_count = min(len(self.product_ids), self.MAX_PRODUCTS) if self.product_ids else 0
        
        if product_count == 0:
            if default_logger:
                default_logger.warning("未找到商品ID，将使用默认评价模板")
            return DEFAULT_COMMENTS[:]
        
        if default_logger:
            default_logger.info("实际爬取商品数量: %d", product_count)

        # 遍历商品
        for j in range(product_count):
            product_id = self.product_ids[j]
            
            if default_logger:
                default_logger.info("正在处理第 %d/%d 个商品 (ID: %s)", j + 1, product_count, product_id)
            
            # 遍历页面
            for page in range(1, max_page + 1):
                if default_logger:
                    default_logger.debug("正在爬取第 %d 页评论", page)
                
                url = self._build_comment_url(product_id, page, score)
                headers = self._get_request_headers(product_id)

                try:
                    response = requests.get(
                        url, 
                        headers=headers,
                        timeout=self.REQUEST_TIMEOUT
                    )
                    response.raise_for_status()
                except requests.RequestException as e:
                    if default_logger:
                        default_logger.warning("请求失败 (商品%s, 第%d页): %s", product_id, page, e)
                    continue

                # 随机延迟，防止被封IP
                delay = random.randint(self.MIN_DELAY, self.MAX_DELAY)
                if default_logger:
                    default_logger.debug("等待 %d 秒...", delay)
                time.sleep(delay)

                if not response.text:
                    if default_logger:
                        default_logger.warning("响应内容为空 (商品%s, 第%d页)", product_id, page)
                    continue

                try:
                    res_json = response.json()
                except json.JSONDecodeError as e:
                    if default_logger:
                        default_logger.warning("JSON解析失败 (商品%s, 第%d页): %s", product_id, page, e)
                    continue

                # 检查是否有评论数据
                img_comments = res_json.get("imgComments", {})
                comment_count = img_comments.get("imgCommentCount", 0)
                
                if comment_count == 0:
                    if default_logger:
                        default_logger.debug("该页无评论数据 (商品%s, 第%d页)", product_id, page)
                    break

                # 提取评论内容
                img_list = img_comments.get("imgList", [])
                for comment_data in img_list:
                    try:
                        comment_vo = comment_data.get("commentVo", {})
                        content = comment_vo.get("content", "").replace("\n", " ").replace("\r", " ")
                        if content:
                            comments.append(content)
                    except (KeyError, AttributeError) as e:
                        if default_logger:
                            default_logger.debug("提取评论失败: %s", e)
                        continue

        if default_logger:
            default_logger.info("共爬取 %d 条%s评价", len(comments), self.comment_types[score])

        # 处理评论，拆分成句子
        result_sentences = self._split_sentences(comments)

        if not result_sentences:
            if default_logger:
                default_logger.warning("未获取到有效评论，使用默认评价模板")
            return DEFAULT_COMMENTS[:]

        return result_sentences

    def _split_sentences(self, comments: list[str]) -> list[str]:
        """
        将评论文本拆分成句子列表
        
        Args:
            comments: 评论文本列表
            
        Returns:
            拆分后的句子列表
        """
        sentences = []
        
        for comment in comments:
            try:
                # 使用 zhon 库按中文标点拆分句子
                found_sentences = re.findall(zhon.hanzi.sentence, comment)
                
                # 过滤无效结果
                if found_sentences and found_sentences not in [
                    ["。"], ["？"], ["！"],
                    ["."], [","], ["?"], ["!"],
                ]:
                    sentences.extend(found_sentences)
                elif default_logger:
                    default_logger.debug("句子拆分结果为空或无效: %s", comment[:50])
            except Exception as e:
                if default_logger:
                    default_logger.debug("句子拆分失败: %s", e)
                # 如果拆分失败，直接添加原评论
                if comment:
                    sentences.append(comment)
        
        if default_logger:
            default_logger.info("最终得到 %d 个句子", len(sentences))
        
        return sentences


# 测试用例
if __name__ == "__main__":
    # 注意：使用前需要设置 cookie
    # from auto_comment_plus import CONFIG_PATH
    # import yaml
    # with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    #     cfg = yaml.safe_load(f)
    # cookie = cfg["user"]["cookie"].encode("utf-8")
    
    test_products = ["手机", "电脑"]
    
    for product_name in test_products:
        print(f"\n{'='*60}")
        print(f"测试商品: {product_name}")
        print('='*60)
        
        try:
            spider = JDSpider(product_name)
            comments = spider.get_data(max_page=2, score=3)
            
            print(f"\n获取到 {len(comments)} 条评论句子:")
            for i, comment in enumerate(comments[:5], 1):  # 只显示前5条
                print(f"  {i}. {comment}")
            
            if len(comments) > 5:
                print(f"  ... 还有 {len(comments) - 5} 条")
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()
