import { LineChart, type TrendChartProps } from "./LineChart";

/** The trend line's fill, as a component (feature 026, layout `type: area`). */
export function AreaChart(props: TrendChartProps) {
  return <LineChart {...props} area />;
}
