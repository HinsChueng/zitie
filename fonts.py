import logging
import os.path
import re

from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfFileMerger

from config import *

logging.basicConfig(format='%(levelname)s:%(asctime)s:%(message)s', level=logging.DEBUG)
logging.getLogger().setLevel(logging.INFO)

CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fa5]+')


class ArticleProducer(object):
	def __init__(self, article, text, author='', only_chinese=True):
		"""
		初始化
		:param article: 文章名称
		:param text: 需要生成字帖的文本
		:param author: 作者
		:param only_chinese: 是否过滤，只保留中文
		"""
		self.article = article
		self.author = author

		self.text = text
		if only_chinese:
			self.text = ''.join(re.findall(CHINESE_PATTERN, text))

		self.offset = (SQUARE_SIZE - FONT_SIZE) / 2
		self.image = None
		self.draw = None
		self.font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

		self._init_painting()
		self.pdf = PdfFileMerger()

	def _init_painting(self):
		"""
		初始化画布
		1、创建空画布
		2、绘制田字格
		"""
		image = Image.new(
			MODE,
			(SQUARE_SIZE * (ROW + 2), SQUARE_SIZE * (LINE + 2)),
			BACK_COLOR
		)

		self.draw = ImageDraw.Draw(image)
		self.image = image

		self.create_table()

	@staticmethod
	def lining(string):
		"""
		将待写入字帖的文本分页, 迭代返回：
		（页码，当前行待写入文本，当前行起始位置，当前行结束位置）

		:param string: 待写入字帖的文本
		:return:
		"""
		total = len(string)
		total_lines, remain = divmod(total, ROW)

		page, line = 0, 0

		for i in range(total_lines):
			line = i % LINE

			if line == 0 and i != 0:
				page += 1

			yield page, line, i * ROW, (i + 1) * ROW

		if (line + 1) % LINE == 0:
			page += 1
			line = 0
		else:
			line += 1

		yield page, line, total_lines * ROW, total_lines * ROW + remain

	def draw_vertical_line(self, x, y1, y2, width, step=1):
		"""
		画田字格中的垂线

		:param x: 横坐标
		:param y1: 纵坐标起始位置
		:param y2: 纵坐标结束位置
		:param width: 垂线宽度
		:param step: 步长，即y的上一次的结束位置和本次的起始位置，用于控制实线和虚线

		:return:
		"""
		for y in range(y1, y2, step):
			self.draw.line([(x, y), (x, y + step / 2)], fill=TABLE_COLOR, width=width)

	def draw_level_line(self, x1, x2, y, width, step=1):
		"""
		画田字格中的水平线

		:param x1: 横坐标起始位置
		:param x2: 横坐标结束位置
		:param y: 纵坐标
		:param width: 垂线宽度
		:param step: 步长，即x的上一次的结束位置和本次的起始位置，用于控制实线和虚线

		:return:
		"""
		for x in range(x1, x2, step):
			self.draw.line([(x, y), (x + step / 2, y)], fill=TABLE_COLOR, width=width)

	def create_table(self):
		"""
		创建田字格

		:return:
		"""
		skip = SQUARE_SIZE / 2

		for x in range(ROW * 2 + 1):
			width, step = (4, 1) if x % 2 == 0 else (1, 8)

			self.draw_vertical_line(
				x=SQUARE_SIZE + x * skip,
				y1=SQUARE_SIZE,
				y2=(LINE + 1) * SQUARE_SIZE,
				width=width,
				step=step
			)

		for y in range(LINE * 2 + 1):
			width, step = (2, 1) if y % 2 == 0 else (1, 8)

			self.draw_level_line(
				x1=SQUARE_SIZE,
				x2=(ROW + 1) * SQUARE_SIZE,
				y=SQUARE_SIZE + y * skip,
				width=width,
				step=step
			)

	def write_line(self, chars, y):
		"""
		把输入文本按照行写入田字格画布

		:param chars: 当前行待写入文本
		:param y: 当前行纵坐标

		:return:
		"""
		for x, ch in enumerate(chars):
			self.draw.text(
				(SQUARE_SIZE * (x + 1) + self.offset, SQUARE_SIZE * (y + 1) + self.offset),
				ch,
				font=self.font,
				fill=FONT_COLOR,
				spacing=SQUARE_SIZE
			)

	def save_image(self, page):
		"""
		将画布写入文件

		:param page: 当前画布的页码

		:return: 文件存储地址
		"""
		save_path = os.path.join(PDF_DIR, self.article)
		self.makedir(save_path)

		self.image.save('%s/%s.%s' % (save_path, page, PIC_SCHEME))

		logging.info('%s 转化为pdf成功！' % save_path)
		return save_path

	def paint(self):
		"""
		把全部输入文本转为田字格字帖，并存到本地
		:return:
		"""
		page, last_page = 0, 0
		pics = []

		for item in [self.author, self.article]:
			if item:
				spacings = self.get_spacings(item)
				self.text = ''.join([item, '\n' * spacings, self.text])

		for page, line, start, end in self.lining(self.text):

			if (line + 1) % LINE == 0:
				self.write_line(self.text[start:end], line)
				path = self.save_image(page)

				last_page = page

				pics.append(path)

				self._init_painting()
			else:
				self.write_line(self.text[start:end], line)

		if page != last_page or page == 0:
			path = self.save_image(page)
			pics.append(path)

		return pics

	@staticmethod
	def get_spacings(string):
		"""
		计算需要设为空格的个数（标题、作者等信息换行时使用）
		:param string:
		:return:
		"""
		return ROW - len(string) % ROW

	@staticmethod
	def makedir(path):
		"""
		创建目录

		:param path: 待创建目录
		:return:
		"""
		if not os.path.exists(path):
			os.makedirs(path)

	@staticmethod
	def del_old_pdfs(path):
		"""
		删除旧的pdf文件（当pdf合并后，即删除单页的文件及其目录）
		:param path:
		:return:
		"""
		for item in os.listdir(path):
			os.remove('%s/%s' % (path, item))

		os.rmdir(path)

	def merge_pdf(self):
		"""
		合并保存的单页pdf，并存储为本地文件

		:return:
		"""
		path = os.path.join(PDF_DIR, self.article)

		self.makedir(path)

		dirs = os.listdir(path)
		dirs.sort()

		for item in dirs:
			self.pdf.append(os.path.join(path, item))

		pdf_dir = '{}/{}.pdf'.format(PDF_DIR, self.article)
		self.pdf.write(pdf_dir)

		logging.info('生成pdf： {}   成功！ \n'.format(pdf_dir))

		self.del_old_pdfs(path)
