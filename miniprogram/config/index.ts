const path = require("path");

const config = {
  projectName: "zhigu",
  date: "2026-7-25",
  designWidth: 375,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2,
    375: 2 / 1,
  },
  sourceRoot: "src",
  outputRoot: "dist",
  plugins: ["@tarojs/plugin-platform-weapp"],
  defineConstants: {},
  copy: {
    patterns: [],
    options: {},
  },
  framework: "react",
  compiler: "webpack5",
  cache: { enable: false },
  mini: {
    postcss: {
      pxtransform: { enable: true, config: {} },
      url: { enable: true, config: { limit: 1024 } },
      cssModules: { enable: false, config: { namingPattern: "module", generateScopedName: "[name]__[local]___[hash:base64:5]" } },
    },
  },
  alias: { "@": path.resolve(__dirname, "..", "src") },
};

module.exports = function (merge) {
  if (process.env.NODE_ENV === "development") {
    return merge({}, config, require("./dev"));
  }
  return merge({}, config, require("./prod"));
};
