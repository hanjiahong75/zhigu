import Taro from "@tarojs/taro";
import "./app.scss";

function App(props: any) {
  Taro.useLaunch(function() {
    console.log("zhigu miniprogram launched");
  });
  return props.children;
}

export default App;