"""测试DeepSeek API - 法律咨询场景"""
import os
from openai import OpenAI


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")

    system_prompt = """你是"百姓法律助手"，一个专业的AI法律咨询顾问。
你精通中国法律法规，包括但不限于：劳动法、婚姻法、合同法、民法典等。
回答时请：
1. 用通俗易懂的语言解释法律问题
2. 引用相关法律条款（如有）
3. 给出实用的建议"""

    print("=" * 60)
    print("百姓法律助手 - AI测试")
    print("=" * 60)

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key, base_url=base_url)

    test_question = "公司没有和我签劳动合同，已经工作3个月了，我该怎么办？"
    print(f"\n用户问题: {test_question}\n")
    print("AI回复中...\n")

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": test_question},
            ],
        )
        print("=" * 60)
        print(response.choices[0].message.content)
        print("=" * 60)
        print("\n测试通过！AI法律助手工作正常")
    except Exception as e:
        print(f"测试失败: {e}")


if __name__ == "__main__":
    main()
