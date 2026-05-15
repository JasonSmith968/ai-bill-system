import os


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


# =========================
# 读取文件
# =========================
def load_bills():

    bills = []

    if not os.path.exists("bills.txt"):
        open("bills.txt", "w", encoding="utf-8").close()

    with open("bills.txt", "r", encoding="utf-8") as file:

        for line in file:

            parts = line.strip().split()

            if len(parts) != 4:
                continue

            bill = {
                "date": parts[0],
                "title": parts[1],
                "money": float(parts[2]),
                "category": parts[3]
            }

            bills.append(bill)

    return bills


# =========================
# 保存文件
# =========================
def save_bills(bills):

    with open("bills.txt", "w", encoding="utf-8") as file:

        for bill in bills:

            file.write(
                f"{bill['date']} "
                f"{bill['title']} "
                f"{bill['money']} "
                f"{bill['category']}\n"
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

        date = input("请输入日期(例如2026-05)：")

        title = input("请输入消费项目：")

        money = float(input("请输入消费金额："))

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

        print("AI识别分类：", category)
        print("添加成功")


    # =========================
    # 查询账单
    # =========================
    elif choice == "2":

        bills = load_bills()

        print("\n===== 当前账单 =====")

        total = 0

        for bill in bills:

            total += bill["money"]

            print("日期：", bill["date"])
            print("消费项目：", bill["title"])
            print("金额：", f"{bill['money']:.2f}")
            print("分类：", bill["category"])
            print()

        print("总消费：", f"{total:.2f}")
# =========================
    # 删除账单
    # =========================
    elif choice == "3":

        bills = load_bills()

        print("\n===== 当前账单 =====")

        show_bills(bills)

        delete_num = int(input("请输入要删除的编号："))

        if delete_num < 1 or delete_num > len(bills):
            print("编号不存在")
            continue

        bills.pop(delete_num - 1)

        save_bills(bills)

        print("删除成功")


    # =========================
    # 分类统计
    # =========================
    elif choice == "4":

        bills = load_bills()

        category_total = {}

        for bill in bills:

            category = bill["category"]
            money = bill["money"]

            if category in category_total:

                category_total[category] += money

            else:

                category_total[category] = money

        print("\n===== 分类统计 =====")

        for category in category_total:

            print(
                category,
                ":",
                f"{category_total[category]:.2f}"
            )


    # =========================
    # 搜索账单
    # =========================
    elif choice == "5":

        keyword = input("请输入搜索关键词：")

        bills = load_bills()

        found = False

        print("\n===== 搜索结果 =====")

        for bill in bills:

            if keyword in bill["title"]:

                print("日期：", bill["date"])
                print("消费项目：", bill["title"])
                print("金额：", f"{bill['money']:.2f}")
                print("分类：", bill["category"])
                print()

                found = True

        if found == False:
            print("没有找到相关账单")


    # =========================
    # 金额排序
    # =========================
    elif choice == "6":

        bills = load_bills()

        print("1. 从高到低")
        print("2. 从低到高")

        sort_choice = input("请选择排序方式：")

        if sort_choice == "1":

            bills.sort(
                key=lambda bill: bill["money"],
                reverse=True
            )

        elif sort_choice == "2":

            bills.sort(
                key=lambda bill: bill["money"]
            )

        print("\n===== 排序结果 =====")

        for bill in bills:

            print("日期：", bill["date"])
            print("消费项目：", bill["title"])
            print("金额：", f"{bill['money']:.2f}")
            print("分类：", bill["category"])
            print()


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