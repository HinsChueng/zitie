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

		self._update_painting()
		self.pdf = PdfFileMerger()

	def _update_painting(self):
		image = Image.new(
			MODE,
			(SQUARE_SIZE * (ROW + 2), SQUARE_SIZE * (LINE + 2)),
			BACK_COLOR
		)

		self.draw = ImageDraw.Draw(image)
		self.image = image

		self.create_table()

	@staticmethod
	def lining(words):
		total = len(words)
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
		for y in range(y1, y2, step):
			self.draw.line([(x, y), (x, y + step / 2)], fill=TABLE_COLOR, width=width)

	def draw_level_line(self, x1, x2, y, width, step=1):
		for x in range(x1, x2, step):
			self.draw.line([(x, y), (x + step / 2, y)], fill=TABLE_COLOR, width=width)

	def create_table(self):
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
		for x, ch in enumerate(chars):
			self.draw.text(
				(SQUARE_SIZE * (x + 1) + self.offset, SQUARE_SIZE * (y + 1) + self.offset),
				ch,
				font=self.font,
				fill=FONT_COLOR,
				spacing=SQUARE_SIZE
			)

	def save_image(self, page):
		save_path = os.path.join(PDF_DIR, self.article)
		self.makedir(save_path)

		self.image.save('%s/%s.%s' % (save_path, page, PIC_SCHEME))

		logging.info('%s 转化为pdf成功！' % save_path)
		return save_path

	def paint(self):
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

				self._update_painting()
			else:
				self.write_line(self.text[start:end], line)

		if page != last_page or page == 0:
			path = self.save_image(page)
			pics.append(path)

		return pics

	@staticmethod
	def get_spacings(name):
		return ROW - len(name) % ROW

	@staticmethod
	def makedir(path):
		if not os.path.exists(path):
			os.makedirs(path)

	@staticmethod
	def del_old_pdfs(path):
		for item in os.listdir(path):
			os.remove('%s/%s' % (path, item))

		os.rmdir(path)

	def merge_pdf(self):

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
