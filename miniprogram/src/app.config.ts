export default defineAppConfig({
  pages: [
    "pages/home/index",
    "pages/market/index",
    "pages/watchlist/index",
    "pages/funds/index",
    "pages/news/index",
    "pages/holdings/index",
  ],
  window: {
    backgroundTextStyle: "dark",
    navigationBarBackgroundColor: "#1677ff",
    navigationBarTitleText: "知股",
    navigationBarTextStyle: "white",
  },
  tabBar: {
    custom: true,
    color: "#999",
    selectedColor: "#1677ff",
    backgroundColor: "#fff",
    borderStyle: "black",
    list: [
      { pagePath: "pages/news/index", text: "新闻" },
      { pagePath: "pages/market/index", text: "行情" },
      { pagePath: "pages/home/index", text: "投研" },
      { pagePath: "pages/watchlist/index", text: "自选" },
      { pagePath: "pages/holdings/index", text: "持有" },
    ],
  },
});