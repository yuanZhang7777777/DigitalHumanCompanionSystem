"""
情感分析服务模块
基于关键词匹配的轻量级情感分析
支持细粒度情感分类（焦虑、迷茫、压力等）
"""
from typing import Dict, Any, List
import re


# 情感关键词库（细粒度分类）
EMOTION_KEYWORDS: Dict[str, List[str]] = {
    # 负面情感
    "焦虑": ["焦虑", "担心", "害怕", "恐惧", "紧张", "不安", "忧虑", "惶恐"],
    "迷茫": ["迷茫", "迷失", "不知道", "不确定", "困惑", "茫然", "无所适从", "不知所措"],
    "压力": ["压力", "压抑", "喘不过气", "太累了", "撑不住", "崩溃", "透不过气"],
    "沮丧": ["沮丧", "失望", "灰心", "心灰意冷", "没意思", "放弃", "绝望", "无望"],
    "孤独": ["孤独", "孤单", "寂寞", "没人", "一个人", "无助", "没有人理解"],
    "愤怒": ["愤怒", "生气", "气死", "烦死", "讨厌", "恨", "愤恨", "不公平"],
    "悲伤": ["难过", "伤心", "哭", "泪", "痛苦", "心痛", "委屈", "难受"],
    # 正面情感
    "开心": ["开心", "高兴", "快乐", "兴奋", "愉快", "喜悦", "棒", "太好了"],
    "平静": ["平静", "还好", "还行", "一般", "普通", "正常", "平常"],
    "期待": ["期待", "希望", "盼望", "憧憬", "向往", "想要", "计划"],
}

# 情感到极性的映射
EMOTION_POLARITY = {
    "焦虑": "negative",
    "迷茫": "negative",
    "压力": "negative",
    "沮丧": "negative",
    "孤独": "negative",
    "愤怒": "negative",
    "悲伤": "negative",
    "开心": "positive",
    "平静": "neutral",
    "期待": "positive",
}


class EmotionService:
    """情感分析服务"""

    def analyze_emotion(self, text: str) -> Dict[str, Any]:
        """
        分析文本的情感状态
        :param text: 输入文本
        :return: 包含 emotion（细粒度）、polarity（极性）、score（置信度）的字典
        """
        if not text or not text.strip():
            return {"emotion": "平静", "polarity": "neutral", "score": 0.5}

        text_lower = text.lower()
        emotion_scores: Dict[str, int] = {}

        for emotion, keywords in EMOTION_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > 0:
                emotion_scores[emotion] = count

        if not emotion_scores:
            return {"emotion": "平静", "polarity": "neutral", "score": 0.3}

        # 取得分最高的情感
        dominant_emotion = max(emotion_scores, key=emotion_scores.get)
        total_matches = sum(emotion_scores.values())
        score = min(1.0, emotion_scores[dominant_emotion] / max(total_matches, 1))

        return {
            "emotion": dominant_emotion,
            "polarity": EMOTION_POLARITY.get(dominant_emotion, "neutral"),
            "score": round(score, 2),
            "all_emotions": emotion_scores,
        }

    def extract_topics(self, text: str) -> List[str]:
        """
        提取文本中的关键话题
        :return: 话题列表（最多3个）
        """
        topic_patterns = {
            "职业规划": ["职业", "工作", "就业", "求职", "职场", "事业", "offer", "面试", "简历"],
            "学业问题": ["学习", "考试", "课程", "作业", "学术", "毕业论文", "答辩", "绩点"],
            "人际关系": ["朋友", "家人", "恋爱", "社交", "关系", "室友", "同学", "导师"],
            "心理健康": ["压力", "焦虑", "抑郁", "情绪", "心理", "崩溃", "撑不住"],
            "未来规划": ["未来", "计划", "目标", "梦想", "方向", "考研", "出国", "创业"],
            "经济压力": ["钱", "工资", "薪资", "贷款", "房租", "生活费", "经济"],
        }

        found_topics = []
        text_lower = text.lower()

        for topic, keywords in topic_patterns.items():
            if any(kw in text_lower for kw in keywords):
                found_topics.append(topic)

        return found_topics[:3]