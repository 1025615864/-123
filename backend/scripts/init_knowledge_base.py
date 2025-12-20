"""初始化法律知识库脚本"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_assistant import get_ai_assistant


def load_law_documents(directory: str) -> list:
    """从目录加载所有法律文档"""
    documents = []
    
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            print(f"📄 加载文件: {filename}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                documents.extend(data)
    
    return documents


def main():
    """主函数"""
    print("=" * 50)
    print("🚀 开始初始化法律知识库")
    print("=" * 50)
    
    knowledge_base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'knowledge_base',
        'laws'
    )
    
    if not os.path.exists(knowledge_base_dir):
        print(f"❌ 目录不存在: {knowledge_base_dir}")
        return
    
    documents = load_law_documents(knowledge_base_dir)
    print(f"\n📚 共加载 {len(documents)} 条法律条文")
    
    if documents:
        print("\n⏳ 正在添加到向量数据库...")
        assistant = get_ai_assistant()
        assistant.knowledge_base.add_law_documents(documents)
        print("✅ 法律知识库初始化完成！")
    else:
        print("⚠️ 没有找到法律文档")
    
    print("\n" + "=" * 50)
    print("📋 测试搜索功能")
    print("=" * 50)
    
    test_query = "劳动合同解除"
    assistant = get_ai_assistant()
    results = assistant.knowledge_base.search(test_query, k=3)
    
    print(f"\n🔍 测试查询: '{test_query}'")
    print(f"📊 找到 {len(results)} 条相关结果:\n")
    
    for i, (content, metadata, score) in enumerate(results, 1):
        print(f"{i}. [{metadata.get('law_name', '未知')} {metadata.get('article', '')}]")
        print(f"   相关度: {1-score:.2f}")
        print(f"   内容: {content[:100]}...")
        print()


if __name__ == "__main__":
    main()
