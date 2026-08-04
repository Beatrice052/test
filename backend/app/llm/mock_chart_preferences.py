"""Keyword chart parsing used only by deterministic local Mock LLM tests."""

from app.presentation.chart_preferences import ChartPreference

_ALIASES: tuple[tuple[str, str], ...] = (
    ("堆叠柱状图", "stacked_bar"),
    ("堆叠条形图", "stacked_bar"),
    ("stacked bar", "stacked_bar"),
    ("热力图", "heatmap"),
    ("heatmap", "heatmap"),
    ("环形图", "donut"),
    ("圆环图", "donut"),
    ("donut", "donut"),
    ("饼图", "donut"),
    ("pie chart", "donut"),
    ("帕累托图", "pareto"),
    ("pareto chart", "pareto"),
    ("pareto", "pareto"),
    ("折线图", "line"),
    ("趋势线", "line"),
    ("line chart", "line"),
    ("柱状图", "bar"),
    ("条形图", "bar"),
    ("bar chart", "bar"),
    ("点图", "dot"),
    ("dot plot", "dot"),
    ("透视表", "pivot"),
    ("pivot table", "pivot"),
    ("表格展示", "table"),
    ("数据表", "table"),
    ("table", "table"),
)

_UNSUPPORTED_ALIASES = (
    "雷达图",
    "桑基图",
    "旭日图",
    "漏斗图",
    "箱线图",
    "地图",
    "radar chart",
    "sankey",
    "sunburst",
    "funnel chart",
    "box plot",
    "散点图",
    "scatter plot",
    "scatter",
)


def parse_chart_preference(message: str) -> ChartPreference:
    """Approximate Agent A behavior for offline demos; never import in the formal path."""

    normalized = message.casefold()
    for label, chart_type in _ALIASES:
        if label.casefold() in normalized:
            return ChartPreference(chart_type=chart_type, user_label=label)
    for label in _UNSUPPORTED_ALIASES:
        if label.casefold() in normalized:
            return ChartPreference(user_label=label, unsupported=True)
    return ChartPreference()
