# =========================
# 自动分类
# =========================
def get_category(title):

    food_keywords = ["咖啡", "奶茶", "炸鸡", "汉堡"]
    transport_keywords = ["公交", "打车", "地铁"]
    entertainment_keywords = ["游戏", "电影"]
    study_keywords = ["课程", "书"]

    for keyword in food_keywords:
        if keyword in title:
            return "饮食"

    for keyword in transport_keywords:
        if keyword in title:
            return "交通"

    for keyword in entertainment_keywords:
        if keyword in title:
            return "娱乐"

    for keyword in study_keywords:
        if keyword in title:
            return "学习"

    return "其他"