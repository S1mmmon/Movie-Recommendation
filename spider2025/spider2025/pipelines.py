# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import openpyxl
import pymysql

class DbPipeline:
    def __init__(self):
        self.conn = pymysql.connect(host='localhost',port=3306,user='root',password='Lzn20040131',database='spider',charset='utf8mb4')
        self.cursor = self.conn.cursor()

    def close_spider(self,spider):
        self.conn.commit()
        self.conn.close()

    def process_item(self,item,spider):
        title = item.get('title', '')
        rank = item.get('rank', '')
        quote = item.get('quote', '无')
        duration = item.get('duration', '')
        intro = item.get('intro', '')
        genre = item.get('genre','')

        try:
            # 执行插入
            self.cursor.execute(
                'INSERT INTO tb_top_movie (title, rating, quote,duration,intro,genre) VALUES (%s, %s, %s, %s, %s, %s)',
                (title, rank, quote,duration,intro,genre)
            )
            # 每次插入都提交（测试时用）
            self.conn.commit()

            # 获取最后插入的ID
            self.cursor.execute("SELECT LAST_INSERT_ID()")
            last_id = self.cursor.fetchone()[0]

            spider.logger.info(f"✅ 成功插入第 {last_id} 条数据: {title}")

        except Exception as e:
            spider.logger.error(f"❌ 插入失败: {e}")
            spider.logger.error(f"   数据: title={title}, rank={rank}")
        return item


class ExcelPipeline:
    def __int__(self):
        self.wb = openpyxl.Workbook()
        self.ws = self.wb.active
        self.ws.title = 'Top250'
        self.ws.append(('标题','评分','名言','时长','简介'))

    def open_spider(self,spider):
        pass

    def close_spider(self,spider):
        self.wb.save('movie.xlsx')

    def process_item(self, item, spider):
        self.ws.append(item['title'],item['rank'],item['quote'],item['duration'],
                       item['intro'],item['title'],)
        return item
