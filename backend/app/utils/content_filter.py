"""内容过滤工具 - 敏感词过滤"""
import re

# 敏感词列表（基础版本，可扩展为从数据库加载）
SENSITIVE_WORDS = [
    # 违法相关
    "代办假证", "办假证", "伪造证件", "假学历", "假文凭",
    "洗钱", "黑钱", "赌博网站", "网络赌博", "六合彩",
    "毒品", "冰毒", "大麻", "可卡因", "海洛因",
    
    # 诈骗相关
    "刷单兼职", "高额返利", "免费领取", "中奖通知",
    
    # 暴力相关
    "杀人方法", "报复社会", "制造炸弹",
    
    # 色情相关
    "色情网站", "成人视频", "约炮",
    
    # 政治敏感（示例，实际需根据法规调整）
    "翻墙软件", "VPN代理",
]

# 广告词汇
AD_WORDS = [
    "加微信", "加QQ", "免费领", "限时优惠", "点击链接",
    "扫码领取", "低价代办", "包过包拿证",
]


class ContentFilter:
    """内容过滤器"""
    
    def __init__(self, custom_words: list[str] | None = None):
        self.sensitive_words: set[str] = set(SENSITIVE_WORDS)
        self.ad_words: set[str] = set(AD_WORDS)
        if custom_words:
            self.sensitive_words.update(custom_words)
    
    def check_content(self, content: str) -> tuple[bool, str, list[str]]:
        """
        检查内容是否包含敏感词
        
        Returns:
            Tuple[bool, str, list[str]]: (是否通过, 原因, 匹配到的敏感词列表)
        """
        if not content:
            return True, "", []
        
        content_lower = content.lower()
        matched_sensitive: list[str] = []
        matched_ads: list[str] = []
        
        # 检查敏感词
        for word in self.sensitive_words:
            if word.lower() in content_lower:
                matched_sensitive.append(word)
        
        # 检查广告词
        for word in self.ad_words:
            if word.lower() in content_lower:
                matched_ads.append(word)
        
        if matched_sensitive:
            return False, "内容包含敏感词汇", matched_sensitive
        
        if len(matched_ads) >= 2:  # 多个广告词才判定
            return False, "内容疑似广告", matched_ads
        
        return True, "", []
    
    def filter_content(self, content: str, replacement: str = "***") -> str:
        """
        过滤敏感词，替换为指定字符
        
        Args:
            content: 原始内容
            replacement: 替换字符
            
        Returns:
            过滤后的内容
        """
        if not content:
            return content
        
        result = content
        all_words = list(self.sensitive_words) + list(self.ad_words)
        
        for word in all_words:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub(replacement, result)
        
        return result
    
    def get_risk_level(self, content: str) -> str:
        """
        获取内容风险等级
        
        Returns:
            'safe' | 'warning' | 'danger'
        """
        passed, _, matched = self.check_content(content)
        
        if passed:
            return 'safe'
        
        if len(matched) >= 3:
            return 'danger'
        
        return 'warning'


# 全局过滤器实例
content_filter = ContentFilter()


def check_post_content(title: str, content: str) -> tuple[bool, str]:
    """
    检查帖子内容
    
    Returns:
        Tuple[bool, str]: (是否通过, 错误信息)
    """
    # 检查标题
    passed, reason, _ = content_filter.check_content(title)
    if not passed:
        return False, f"标题{reason}"
    
    # 检查内容
    passed, reason, _ = content_filter.check_content(content)
    if not passed:
        return False, f"内容{reason}"
    
    return True, ""


def check_comment_content(content: str) -> tuple[bool, str]:
    """
    检查评论内容
    
    Returns:
        Tuple[bool, str]: (是否通过, 错误信息)
    """
    passed, reason, _ = content_filter.check_content(content)
    if not passed:
        return False, reason
    
    return True, ""


def needs_review(content: str) -> tuple[bool, str]:
    """
    判断内容是否需要人工审核
    
    Returns:
        Tuple[bool, str]: (是否需要审核, 原因)
    """
    risk_level = content_filter.get_risk_level(content)
    
    if risk_level == 'danger':
        return True, "内容风险较高，需要人工审核"
    
    # 检查是否包含链接
    url_pattern = r'https?://[^\s]+'
    if re.search(url_pattern, content):
        return True, "内容包含链接，需要人工审核"
    
    # 检查是否包含联系方式
    phone_pattern = r'1[3-9]\d{9}'
    if re.search(phone_pattern, content):
        return True, "内容包含联系方式，需要人工审核"
    
    return False, ""


def add_sensitive_word(word: str):
    """添加敏感词"""
    content_filter.sensitive_words.add(word)


def remove_sensitive_word(word: str):
    """移除敏感词"""
    content_filter.sensitive_words.discard(word)


def get_all_sensitive_words() -> list[str]:
    """获取所有敏感词"""
    return list(content_filter.sensitive_words)


def add_ad_word(word: str):
    """添加广告词"""
    content_filter.ad_words.add(word)


def remove_ad_word(word: str):
    """移除广告词"""
    content_filter.ad_words.discard(word)


def get_all_ad_words() -> list[str]:
    """获取所有广告词"""
    return list(content_filter.ad_words)
