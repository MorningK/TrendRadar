# coding=utf-8
"""主程序入口"""

from src.news_analyzer import NewsAnalyzer, CONFIG


def main():
    try:
        analyzer = NewsAnalyzer()
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ 配置文件错误: {e}")
        print("\n请确保以下文件存在:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\n参考项目文档进行正确配置")
    except Exception as e:
        print(f"❌ 程序运行错误: {e}")
        raise


if __name__ == "__main__":
    main()