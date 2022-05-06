### zitie 生成田字格字帖

###### 注：默认为田英章硬笔楷书，可自行导入字体包放到fonts目录，并修改配置文件进行更换

### 运行项目

##### 1、安装依赖:

```bash
pip install -r requirements.txt
```

##### 2、更新配置:

```bash
vim config.py
```

```python
# 字帖相关
# 田字格大小
SQUARE_SIZE = 120

# 字体大小
FONT_SIZE = 100

# 字体颜色
FONT_COLOR = 'black'

# 田字格颜色
TABLE_COLOR = 'red'

# 背景颜色
BACK_COLOR = 'white'

# 每页行数
LINE = 10

# 每页列数
ROW = 10

# 色彩模式
MODE = 'RGB'

# 文件相关
# 字体文件位置
FONT_PATH = './fonts/tk.ttf'

# 保存图片格式
PIC_SCHEME = 'pdf'

# 图片存放目录
PDF_DIR = './pdf'

```

### 3、运行

```bash
python main.py
```