import os
import sys
from fonts import ArticleProducer

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def run():
	article = input('请输入待处理文章名称：\n')
	text = input('请输入待处理文章内容：\n')

	producer = ArticleProducer(article=article, text=text)

	producer.paint()

	producer.merge_pdf()


if __name__ == '__main__':
	run()
