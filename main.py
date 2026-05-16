import os

import json
# 自动分类
# =========================
def get_category(title):

    if "咖啡" in title:
        return "饮食"

    elif "奶茶" in title:
        return "饮食"

    elif "炸鸡" in title:
        return "饮食"

    elif "汉堡" in title:
        return "饮食"

    elif "公交" in title:
        return "交通"

    elif "打车" in title:
        return "交通"

    elif "地铁" in title:
        return "交通"

    elif "游戏" in title:
        return "娱乐"

    elif "电影" in title:
        return "娱乐"

    elif "课程" in title:
        return "学习"

    elif "书" in title:
        return "学习"

    else:
        return "其他"

# =====================
# 读取账单
# =====================

def load_bills():

    if not os.path.exists("bills.json"):

        return []

    with open(
        "bills.json",
        "r",
        encoding="utf-8"
    ) as file:

        bills = json.load(file)

    return bills

# =====================
# 保存账单
# =====================

def save_bills(bills):

    with open(
        "bills.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            bills,
            file,
            ensure_ascii=False,
            indent=4
        )

# =========================
# 打印账单
# =========================
def show_bills(bills):

    if len(bills) == 0:
        print("暂无账单")
        return

    for index, bill in enumerate(bills):

        print(
            index + 1,
            bill["date"],
            bill["title"],
            f"{bill['money']:.2f}",
            bill["category"]
        )

# =====================
# 添加账单
# =====================

def  add_bill():

    date = input("请输入日期(例如2026-05): ")

    title = input("请输入消费项目: ")

    money = float(input("请输入消费金额: "))

    category = get_category(title)

    bill = {
        "date": date,
        "title": title,
        "money": money,
        "category": category
    }

    bills = load_bills()

    bills.append(bill)

    save_bills(bills)

    print("AI识别分类:", category)
    print("添加成功")
    return category

# =====================
# 查询账单
# =====================

def query_bills():

    bills = load_bills()

    if len(bills) == 0:
        print("暂无账单")
        return

    print("\n===== 当前账单 =====")

    total = 0

    for index, bill in enumerate(bills):

        total += bill["money"]

        print(
            index + 1,
            bill["date"],
            bill["title"],
            f"{bill['money']:.2f}",
            bill["category"]
        )

    print("\n总消费:", f"{total:.2f}")

# =====================
# 删除账单
# =====================

def delete_bill():

    bills = load_bills()

    if len(bills) == 0:
        print("暂无账单")
        return

    # 先显示账单
    query_bills()

    try:

        index = int(input("\n请输入要删除的账单编号: "))

        # 编号转索引
        real_index = index - 1

        # 判断是否越界
        if real_index < 0 or real_index >= len(bills):

            print("编号不存在")
            return

        # 删除数据
        deleted_bill = bills.pop(real_index)

        # 保存文件
        save_bills(bills)

        print("删除成功:", deleted_bill["title"])

    except:

        print("输入错误")

# =====================
# 搜索账单
# =====================

def search_bill():

    bills = load_bills()

    if len(bills) == 0:

        print("暂无账单")
        return

    keyword = input("请输入搜索关键词: ")

    found = False

    print("\n===== 搜索结果 =====")

    for bill in bills:

        # 模糊搜索
        if keyword in bill["title"]:

            found = True

            print(
                bill["date"],
                bill["title"],
                f"{bill['money']:.2f}",
                bill["category"]
            )

    if not found:

        print("未找到相关账单")

# =====================
# 分类统计
# =====================

def category_statistics():

    bills = load_bills()

    if len(bills) == 0:

        print("暂无账单")
        return

    # 统计字典
    statistics = {}

    # 开始统计
    for bill in bills:

        category = bill["category"]

        money = bill["money"]

        # 如果分类不存在
        if category not in statistics:

            statistics[category] = 0

        # 累加金额
        statistics[category] += money

    print("\n===== 分类统计 =====")

    total = 0

    for category, money in statistics.items():

        total += money

        print(f"{category}: {money:.2f}")

    print("\n总消费:", f"{total:.2f}")

# =====================
# 月度统计
# =====================

def month_statistics():

    bills = load_bills()

    if len(bills) == 0:

        print("暂无账单")
        return

    month = input("请输入月份(例如2026-05): ")

    total = 0

    found = False

    print(f"\n===== {month} 月账单 =====")

    for bill in bills:

        # 判断月份
        if bill["date"] == month:

            found = True

            total += bill["money"]

            print(
                bill["title"],
                f"{bill['money']:.2f}",
                bill["category"]
            )

    if not found:

        print("该月份暂无账单")
        return

    print(f"\n{month} 总消费:", f"{total:.2f}")


# =========================
# 主循环
# =========================
while True:

    print("\n===== AI记账系统 =====")
    print("1. 添加账单")
    print("2. 查询账单")
    print("3. 删除账单")
    print("4. 分类统计")
    print("5. 搜索账单")
    print("6. 金额排序")
    print("7. 最高消费")
    print("8. 月度统计")
    print("9. 修改账单")
    print("10. 清空账单")
    print("11. 退出系统")

    choice = input("请输入功能编号：")


    # =========================
    # 添加账单
    # =========================
    if choice == "1":

        add_bill()

    # =========================
    # 查询账单
    # =========================
    elif choice == "2":

        query_bills()

# =========================
    # 删除账单
    # =========================
    elif choice == "3":

        delete_bill()

    # =========================
    # 分类统计
    # =========================
    elif choice == "4":

        category_statistics()

    # =========================
    # 搜索账单
    # =========================
    elif choice == "5":

        search_bill()

    # =========================
    # 金额排序
    # =========================
    elif choice == "6":

        month_statistics()

    # =========================
    # 最高消费
    # =========================
    elif choice == "7":

        bills = load_bills()

        if len(bills) == 0:
            print("暂无账单")
            continue

        max_bill = bills[0]

        for bill in bills:

            if bill["money"] > max_bill["money"]:

                max_bill = bill

        print("\n===== 最高消费 =====")

        print("日期：", max_bill["date"])
        print("消费项目：", max_bill["title"])
        print("金额：", f"{max_bill['money']:.2f}")
        print("分类：", max_bill["category"])
# =========================
    # 月度统计
    # =========================
    elif choice == "8":

        month = input("请输入月份(例如2026-05)：")

        bills = load_bills()

        total = 0

        for bill in bills:

            if bill["date"] == month:

                total += bill["money"]

        print()

        print(month, "总消费：", f"{total:.2f}")


    # =========================
    # 修改账单
    # =========================
    elif choice == "9":

        bills = load_bills()

        print("\n===== 当前账单 =====")

        show_bills(bills)

        edit_num = int(input("请输入修改编号："))

        if edit_num < 1 or edit_num > len(bills):
            print("编号不存在")
            continue

        bill = bills[edit_num - 1]

        print("当前项目：", bill["title"])

        new_title = input("请输入新的消费项目：")

        new_money = float(input("请输入新的金额："))

        new_category = get_category(new_title)

        bill["title"] = new_title
        bill["money"] = new_money
        bill["category"] = new_category

        save_bills(bills)

        print("修改成功")


    # =========================
    # 清空账单
    # =========================
    elif choice == "10":

        confirm = input("确定清空所有账单？(y/n)：")

        if confirm == "y":

            open("bills.txt", "w", encoding="utf-8").close()

            print("已清空")

        else:

            print("已取消")


    # =========================
    # 退出系统
    # =========================
    elif choice == "11":

        print("退出系统")

        break


    else:

        print("输入错误")