import pandas as pd

# 尝试不同编码读取
encodings = ['utf-8', 'gbk', 'gb2312', 'latin1', 'cp1252']
for enc in encodings:
    try:
        df = pd.read_csv('C:/Users\Lzn\Desktop\spider2025\电影数据.csv', encoding=enc)
        df.to_csv('C:/Users\Lzn\Desktop\spider2025\电影数据.csv', encoding='utf-8-sig', index=False)
        print(f"成功使用 {enc} 编码读取")
        break
    except:
        continue