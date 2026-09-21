import { useEffect, useState } from "react";

/* 手机断点：宽 < 768px；另外把"触摸设备 + 矮视口"（手机横屏）也算作手机布局。
   桌面端（宽 >=768px 且鼠标指针）的布局与行为完全不受影响。 */
export const MOBILE_QUERY =
  "(max-width: 767.98px), (max-height: 520px) and (pointer: coarse)";

/** True below the 768px breakpoint — phone layout (bottom tab bar + overlay drawers). */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(() => window.matchMedia(MOBILE_QUERY).matches);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY);
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    setIsMobile(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return isMobile;
}
