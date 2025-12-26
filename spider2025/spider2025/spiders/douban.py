import scrapy
from scrapy import Selector,Request
from spider2025.items import MovieItem


class DoubanSpider(scrapy.Spider):
    name = "douban"
    allowed_domains = ["movie.douban.com"]
    #start_urls = ["https://movie.douban.com/top250"]

    def start_requests(self):
        for page in range(10):
            yield Request(url=f'https://movie.douban.com/top250?start={page*25}&filter=')

    def parse(self,response):
        sel = Selector(response)
        list_items = sel.css('#content > div > div.article > ol > li')
        for list_item in list_items:

            detail_url = list_item.css('div.info > div.hd > a::attr(href)').extract_first()

            movie_item = MovieItem()
            movie_item['title'] = list_item.css('span.title::text').extract_first()
            movie_item['rank']  = list_item.css('span.rating_num::text').extract_first()
            movie_item['quote'] = list_item.css('p.quote span::text').get()
            movie_item['genre'] =list_item.xpath('//div[@class="bd"]/p/br/following-sibling::text()').get()

            yield Request(
                url= detail_url,callback=self.parse_drtail,
                cb_kwargs = {'item': movie_item}
            )

    def parse_drtail(self,response,**kwargs):
        movie_item = kwargs['item']
        sel = Selector(response)
        movie_item['duration'] = sel.css('span[property="v:runtime"]::attr(content)').extract_first()
        movie_item['intro'] = sel.css('span[property="v:summary"]::text').get()
        yield movie_item

#终端运行：scrapy crawl douban -o douban.csv