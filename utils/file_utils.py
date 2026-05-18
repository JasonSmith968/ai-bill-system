import os
import json


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