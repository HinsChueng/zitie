import os
import sys
from fonts import ArticleProducer

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def run():
	# article = input('请输入待处理文章名称：\n')
	# text = input('请输入待处理文章内容：\n')
	text = '　　楚人伐宋以救郑。宋公将战。大司马固谏曰：“天之弃商久矣，君将兴之，弗可赦也已。”弗听。冬十一月己巳朔，宋公及楚人战于泓。宋人既成列，楚人未既济。司马曰：“彼众我寡，及其未既济也，请击之。”公曰：“不可。”既济而未成列，又以告。公曰：“未可。”既陈而后击之，宋师败绩。公伤股，门官歼焉。　　国人皆咎公。公曰：“君子不重伤，不禽二毛。古之为军也，不以阻隘也。寡人虽亡国之余，不鼓不成列。”子鱼曰：“君未知战。勍敌之人，隘而不列，天赞我也。阻而鼓之，不亦可乎？犹有惧焉！且今之勍者，皆我敌也。虽及胡耇，获则取之，何有于二毛？明耻教战，求杀敌也。伤未及死，如何勿重？若爱重伤，则如勿伤；爱其二毛，则如服焉。三军以利用也，金鼓以声气也。利而用之，阻隘可也；声盛致志，鼓儳可也。” '
	article = '子鱼论战'
	producer = ArticleProducer(article=article, text=text)
	producer.paint()
	producer.merge_pdf()


if __name__ == '__main__':
	run()
