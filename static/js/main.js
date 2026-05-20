// 分类统计
const categoryCtx =
    document.getElementById(
        "categoryChart"
    );

if (categoryCtx) {

    new Chart(categoryCtx, {

        type: "pie",

        data: {

            labels: categoryLabels,

            datasets: [
                {

                    data: categoryValues
                }
            ]
        }
    });
}


// 月度趋势
const trendCtx =
    document.getElementById(
        "trendChart"
    );

if (trendCtx) {

    new Chart(trendCtx, {

        type: "line",

        data: {

            labels: trendLabels,

            datasets: [
                {

                    label: "消费金额",

                    data: trendValues,

                    tension: 0.3
                }
            ]
        }
    });
}