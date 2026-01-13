// i18n 国际化配置
import { zh } from './zh';
import { en } from './en';

export type Language = 'zh' | 'en';
export type TranslationKeys = typeof zh;

const translations: Record<Language, TranslationKeys> = {
  zh,
  en,
};

// 获取嵌套键值
export function getNestedValue(obj: any, path: string): string {
  const keys = path.split('.');
  let result = obj;
  for (const key of keys) {
    if (result && typeof result === 'object' && key in result) {
      result = result[key];
    } else {
      return path; // 返回原始路径作为fallback
    }
  }
  return typeof result === 'string' ? result : path;
}

// 翻译函数
export function translate(lang: Language, key: string): string {
  const primary = getNestedValue(translations[lang], key);
  if (primary !== key) return primary;
  if (lang !== 'zh') {
    const fallback = getNestedValue(translations.zh, key);
    if (fallback !== key) return fallback;
  }
  return primary;
}

// 获取所有翻译
export function getTranslations(lang: Language): TranslationKeys {
  return translations[lang];
}

// 检测浏览器语言
export function detectBrowserLanguage(): Language {
  const browserLang = navigator.language.toLowerCase();
  if (browserLang.startsWith('zh')) {
    return 'zh';
  }
  return 'en';
}

// 从localStorage获取语言设置
export function getSavedLanguage(): Language {
  try {
    const saved = localStorage.getItem('language');
    if (saved === 'zh' || saved === 'en') {
      return saved;
    }
  } catch {
    // ignore
  }
  return detectBrowserLanguage();
}

// 保存语言设置
export function saveLanguage(lang: Language): void {
  try {
    localStorage.setItem('language', lang);
  } catch {
    // ignore
  }
}

export { zh, en };
