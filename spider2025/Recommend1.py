import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import re
from typing import List, Dict


class SimpleNLPRecommender:
    """
    简洁的NLP电影推荐器
    核心：paraphrase-MiniLM-L3-v2 + 文本特征 + 评分
    """

    def __init__(self, df, model_name='paraphrase-MiniLM-L3-v2'):
        """
        初始化推荐器

        Args:
            df: 电影数据
            model_name: 使用L12-v2（比L3-v2更快，效果接近）
        """
        self.df = self._prepare_data(df.copy())
        self.model = None
        self.genre_mapping = {}
        self.model_name = model_name
        # 初始化模型和特征
        self._initialize()

    def _prepare_data(self, df):
        """数据预处理"""
        # 确保关键字段
        df['rating'] = pd.to_numeric(df['rating'], errors='coerce').fillna(df['rating'].median())
        df['duration'] = pd.to_numeric(df['duration'], errors='coerce').fillna(df['duration'].median())

        # 创建综合文本（quote + intro）
        df['combined_text'] = df.apply(
            lambda row: f"{row['quote'] if pd.notna(row['quote']) else ''} "
                        f"{row['intro'] if pd.notna(row['intro']) else ''}".strip(),
            axis=1
        )

        # 提取体裁列表
        df['genre_list'] = df['genre'].apply(self._extract_genres)

        return df

    def _extract_genres(self, genre_str):
        """提取体裁"""
        if pd.isna(genre_str):
            return []

        parts = str(genre_str).split('/')
        if len(parts) >= 3:
            genre_part = parts[-1].strip()
        else:
            genre_part = str(genre_str)

        # 分割并清理
        genres = re.split(r'[\s、,，]+', genre_part)
        return [g.strip() for g in genres if g.strip() and len(g) > 1]

    def _initialize(self):
        """初始化模型和特征"""
        print("正在初始化NLP推荐系统...")

        # 1. 加载模型
        try:
            self.model = SentenceTransformer(self.model_name)
            print(f"✅ 模型 '{self.model_name}' 加载成功")
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            raise

        # 2. 提取所有体裁
        all_genres = set()
        for genres in self.df['genre_list']:
            all_genres.update(genres)
        self.all_genres = sorted(list(all_genres))
        print(f"📚 发现 {len(self.all_genres)} 种体裁")

        # 3. 预计算体裁特征
        print("正在预计算体裁特征...")
        self._precompute_genre_features()

        print("✅ 系统初始化完成")

    def _precompute_genre_features(self):
        """预计算每个体裁的特征向量"""
        # 为每个体裁构建描述
        genre_descriptions = {}

        for genre in self.all_genres:
            # 找到该体裁的电影
            genre_movies = []
            for idx, row in self.df.iterrows():
                if genre in row['genre_list']:
                    genre_movies.append({
                        'idx': idx,
                        'text': row['combined_text'],
                        'rating': row['rating']
                    })

            if genre_movies:
                # 提取该体裁的文本特征
                texts = [movie['text'] for movie in genre_movies if movie['text']]
                if texts:
                    # 使用模型生成体裁特征向量
                    genre_embeddings = self.model.encode(texts)
                    # 取平均作为体裁特征
                    genre_vector = np.mean(genre_embeddings, axis=0)

                    # 存储
                    self.genre_mapping[genre] = {
                        'vector': genre_vector,
                        'movie_indices': [m['idx'] for m in genre_movies],
                        'avg_rating': np.mean([m['rating'] for m in genre_movies])
                    }

    def get_all_genres(self) -> List[str]:
        """获取所有可用体裁"""
        return self.all_genres

    def recommend_one_movie(self,
                            genre: str,
                            user_preference: str = None,
                            strategy: str = "balanced") -> Dict:
        """
        推荐一部电影

        Args:
            genre: 目标体裁
            user_preference: 用户额外描述（可选）
            strategy: 策略
                - "text_first": 文本相似度优先
                - "rating_first": 评分优先
                - "balanced": 平衡考虑

        Returns:
            推荐电影信息
        """
        # 1. 检查体裁
        if genre not in self.genre_mapping:
            # 尝试模糊匹配
            similar = [g for g in self.all_genres if genre in g]
            if not similar:
                return {
                    'success': False,
                    'error': f"未找到体裁 '{genre}'",
                    'suggestions': self.all_genres[:10]
                }
            genre = similar[0]
            print(f"📝 使用 '{genre}' 代替")

        # 2. 获取该体裁的电影
        genre_info = self.genre_mapping[genre]
        movie_indices = genre_info['movie_indices']

        if not movie_indices:
            return {'success': False, 'error': f"体裁 '{genre}' 下没有电影"}

        # 3. 如果有用户偏好，计算匹配度
        if user_preference:
            # 生成用户偏好的向量
            user_vector = self.model.encode([user_preference])[0]

            # 计算每部电影的匹配分数
            scores = []
            for idx in movie_indices:
                movie = self.df.iloc[idx]

                # 文本相似度（如果有文本）
                text_similarity = 0.5  # 默认值
                if movie['combined_text']:
                    movie_vector = self.model.encode([movie['combined_text']])[0]
                    text_similarity = self._cosine_similarity(user_vector, movie_vector)

                # 评分分数（归一化）
                rating_score = movie['rating'] / 10.0

                # 根据策略计算综合分数
                if strategy == "text_first":
                    final_score = 0.7 * text_similarity + 0.3 * rating_score
                elif strategy == "rating_first":
                    final_score = 0.3 * text_similarity + 0.7 * rating_score
                else:  # balanced
                    final_score = 0.5 * text_similarity + 0.5 * rating_score

                scores.append((idx, final_score, text_similarity, rating_score))

            # 按综合分数排序
            scores.sort(key=lambda x: x[1], reverse=True)
            best_idx, best_score, text_sim, rating_score = scores[0]

        else:
            # 4. 没有用户偏好，按评分排序
            scored_movies = []
            for idx in movie_indices:
                movie = self.df.iloc[idx]
                scored_movies.append((idx, movie['rating']))

            scored_movies.sort(key=lambda x: x[1], reverse=True)
            best_idx, best_score = scored_movies[0]
            text_sim, rating_score = 0.5, best_score / 10.0

        # 5. 获取电影信息
        movie = self.df.iloc[best_idx]

        # 6. 生成推荐理由
        reason = self._generate_reason(movie, genre, user_preference,
                                       text_sim if user_preference else None)

        return {
            'success': True,
            'genre': genre,
            'title': movie['title'],
            'rating': float(movie['rating']),
            'duration': int(movie['duration']) if not pd.isna(movie['duration']) else 0,
            'quote': movie['quote'] if pd.notna(movie['quote']) else "",
            'intro_preview': str(movie['intro'])[:150] + "..." if len(str(movie['intro'])) > 150 else str(
                movie['intro']),
            'genres': movie['genre_list'],
            'match_score': float(best_score),
            'text_similarity': float(text_sim) if user_preference else None,
            'recommendation_reason': reason,
            'strategy': strategy
        }

    def _cosine_similarity(self, vec1, vec2):
        """计算余弦相似度"""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def _generate_reason(self, movie, genre, user_preference, text_similarity=None):
        """生成推荐理由"""
        reasons = []

        # 评分理由
        if movie['rating'] >= 9.0:
            reasons.append("超高评分作品")
        elif movie['rating'] >= 8.5:
            reasons.append("高分佳作")

        # 文本匹配理由
        if text_similarity and text_similarity > 0.7:
            reasons.append("与您的描述高度匹配")
        elif text_similarity and text_similarity > 0.5:
            reasons.append("符合您的偏好")

        # 体裁多样性
        if len(movie['genre_list']) > 1:
            other_genres = [g for g in movie['genre_list'] if g != genre]
            if other_genres:
                reasons.append(f"融合{', '.join(other_genres[:2])}等元素")

        # 标语吸引力
        if movie['quote'] and len(str(movie['quote'])) > 5:
            reasons.append("标语深刻")

        if not reasons:
            reasons.append(f"经典{genre}电影")

        return " • ".join(reasons[:3])


def display_recommendation(result):
    """显示推荐结果"""
    print("\n" + "🎬" * 35)
    print("🎬          电 影 推 荐           🎬")
    print("🎬" * 35)

    if not result['success']:
        print(f"\n❌ {result['error']}")
        if 'suggestions' in result:
            print(f"\n💡 试试这些体裁：{', '.join(result['suggestions'])}")
        return

    print(f"\n🏆 推荐电影：《{result['title']}》")
    print(f"⭐ 评分：{result['rating']}/10")
    print(f"🏷 主体裁：{result['genre']}")

    if len(result['genres']) > 1:
        other_genres = [g for g in result['genres'] if g != result['genre']]
        if other_genres:
            print(f"   🔗 其他体裁：{', '.join(other_genres)}")

    print(f"⏱ 时长：{result['duration']}分钟")
    print(f"📊 匹配度：{result['match_score']:.3f}")

    if result['text_similarity']:
        print(f"   📝 文本相似度：{result['text_similarity']:.3f}")

    if result['quote']:
        print(f"\n💬 标语：{result['quote']}")

    if result['intro_preview']:
        print(f"\n📖 简介：{result['intro_preview']}")

    print(f"\n🎯 推荐理由：{result['recommendation_reason']}")
    print(f"🔧 策略：{result['strategy']}")

    print("\n" + "🎬" * 35)


def simple_interactive():
    """简洁的交互界面"""
    # 假设df已经加载
    print("🚀 NLP电影推荐系统")
    print("=" * 50)

    # 初始化
    print("正在加载模型...（首次使用需要下载）")
    recommender = SimpleNLPRecommender(df)

    # 显示体裁
    all_genres = recommender.get_all_genres()
    print(f"\n📚 可用体裁 ({len(all_genres)}种):")

    # 分组显示
    for i in range(0, len(all_genres), 10):
        chunk = all_genres[i:i + 10]
        print("  " + "  ".join([f"{g:8}" for g in chunk]))

    print("\n" + "=" * 50)

    while True:
        print("\n🎯 请输入体裁：")
        genre = input("👉 ").strip()

        if genre.lower() in ['q', 'quit', '退出']:
            print("👋 再见！")
            break

        if genre.lower() in ['list', '列表']:
            for i, g in enumerate(all_genres, 1):
                print(f"{i:3d}. {g}")
            continue

        print("💭 可选：描述你的偏好（直接回车跳过）：")
        preference = input("👉 ").strip() or None

        if preference:
            print("⚖️  选择策略：1.文本优先 2.评分优先 3.平衡（默认）")
            strategy_choice = input("👉 ").strip()
            if strategy_choice == '1':
                strategy = "text_first"
            elif strategy_choice == '2':
                strategy = "rating_first"
            else:
                strategy = "balanced"
        else:
            strategy = "balanced"

        print(f"\n🔍 正在分析{genre}电影...")
        if preference:
            print(f"   分析偏好：'{preference}'")

        result = recommender.recommend_one_movie(genre, preference, strategy)
        display_recommendation(result)


# 🚀 快速使用示例
def quick_demo():
    """快速演示"""
    print("🎬 NLP推荐演示")
    print("=" * 40)

    recommender = SimpleNLPRecommender(df)

    # 演示案例
    cases = [
        ("犯罪", None, "评分优先"),
        ("爱情", "浪漫温馨", "文本优先"),
        ("科幻", "宇宙探索", "平衡"),
        ("动画", "治愈温暖", "文本优先"),
        ("剧情", "人生思考", "平衡")
    ]

    for genre, preference, strategy in cases:
        print(f"\n🔍 {genre} | 偏好：{preference or '无'} | 策略：{strategy}")
        print("-" * 40)

        result = recommender.recommend_one_movie(genre, preference, strategy)

        if result['success']:
            print(f"🎬 《{result['title']}》 ⭐{result['rating']}")
            print(f"   📊 匹配度：{result['match_score']:.3f}")
            if result['quote']:
                print(f"   💬 {result['quote'][:50]}...")
        else:
            print(f"❌ {result['error']}")





if __name__ == "__main__":
    df = pd.read_csv('C:/Users\Lzn\Desktop\spider2025\电影数据.csv')
    simple_interactive()

