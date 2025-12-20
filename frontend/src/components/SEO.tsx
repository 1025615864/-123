// SEO 组件 - 用于设置页面标题和元数据
import { useEffect } from 'react';

interface SEOProps {
  title?: string;
  description?: string;
  keywords?: string[];
  image?: string;
  url?: string;
  type?: 'website' | 'article';
}

const DEFAULT_TITLE = '百姓法律助手';
const DEFAULT_DESCRIPTION = '一站式法律服务平台，提供AI法律咨询、论坛交流、法律资讯、律所查询等服务';
const DEFAULT_KEYWORDS = ['法律咨询', '律师', 'AI法律助手', '法律服务', '律所查询'];

export function SEO({
  title,
  description = DEFAULT_DESCRIPTION,
  keywords = DEFAULT_KEYWORDS,
  image,
  url,
  type = 'website',
}: SEOProps) {
  const fullTitle = title ? `${title} - ${DEFAULT_TITLE}` : DEFAULT_TITLE;

  useEffect(() => {
    // 设置标题
    document.title = fullTitle;

    // 设置 meta 标签
    const setMeta = (name: string, content: string) => {
      let meta = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement;
      if (!meta) {
        meta = document.createElement('meta');
        meta.name = name;
        document.head.appendChild(meta);
      }
      meta.content = content;
    };

    const setProperty = (property: string, content: string) => {
      let meta = document.querySelector(`meta[property="${property}"]`) as HTMLMetaElement;
      if (!meta) {
        meta = document.createElement('meta');
        meta.setAttribute('property', property);
        document.head.appendChild(meta);
      }
      meta.content = content;
    };

    // 基础 meta
    setMeta('description', description);
    setMeta('keywords', keywords.join(', '));

    // Open Graph
    setProperty('og:title', fullTitle);
    setProperty('og:description', description);
    setProperty('og:type', type);
    if (url) setProperty('og:url', url);
    if (image) setProperty('og:image', image);

    // Twitter Card
    setMeta('twitter:card', 'summary_large_image');
    setMeta('twitter:title', fullTitle);
    setMeta('twitter:description', description);
    if (image) setMeta('twitter:image', image);

    // 清理函数
    return () => {
      document.title = DEFAULT_TITLE;
    };
  }, [fullTitle, description, keywords, image, url, type]);

  return null;
}

// 预定义的页面SEO配置
export const pageSEO = {
  home: {
    title: undefined,
    description: '百姓法律助手 - 一站式法律服务平台，提供AI法律咨询、论坛交流、法律资讯、律所查询等服务',
    keywords: ['法律咨询', '律师', 'AI法律助手', '法律服务', '百姓法律'],
  },
  chat: {
    title: 'AI法律咨询',
    description: '智能AI法律顾问，快速解答您的法律问题，提供专业的法律建议',
    keywords: ['AI法律咨询', '智能律师', '法律问答', '在线咨询'],
  },
  forum: {
    title: '法律论坛',
    description: '法律问题讨论社区，与他人交流法律经验，获取专业解答',
    keywords: ['法律论坛', '法律社区', '法律讨论', '法律问答'],
  },
  news: {
    title: '法律资讯',
    description: '最新法律新闻动态，法规政策解读，案例分析',
    keywords: ['法律新闻', '法律资讯', '法规政策', '案例分析'],
  },
  lawfirm: {
    title: '律所查询',
    description: '查找附近律师事务所，预约专业律师咨询',
    keywords: ['律师事务所', '律师查询', '律所', '找律师'],
  },
  calculator: {
    title: '诉讼费计算器',
    description: '在线计算诉讼费用，包括案件受理费、申请费等',
    keywords: ['诉讼费计算', '律师费计算', '案件费用'],
  },
  documents: {
    title: '法律文书生成',
    description: '智能生成各类法律文书，包括合同、起诉状、答辩状等',
    keywords: ['法律文书', '合同模板', '起诉状', '法律文档'],
  },
};

export default SEO;
