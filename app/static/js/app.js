(() => {
  "use strict";

  const STORAGE_KEY = "chatbi-mock-session-v1";
  const MAX_STORED_MESSAGES = 20;
  const form = document.querySelector("#chat-form");
  const input = document.querySelector("#message-input");
  const sendButton = document.querySelector("#send-button");
  const clearButton = document.querySelector("#clear-conversation");
  const conversation = document.querySelector("#conversation");
  const loading = document.querySelector("#loading");
  const template = document.querySelector("#message-template");
  const exampleButtons = document.querySelectorAll(".example-question");
  const dataSourceMode = document.body.dataset.sourceMode || "mock";

  let requestInFlight = false;
  let chartSequence = 0;
  const chartInstances = new Set();
  const restored = restoreSession();
  let sessionId = restored.sessionId || createSessionId();
  let messageHistory = restored.messages || [];
  document.documentElement.dataset.chatbiReady = "true";

  function createSessionId() {
    if (globalThis.crypto?.randomUUID) {
      return `session-${globalThis.crypto.randomUUID()}`;
    }
    return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function restoreSession() {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
      return {
        sessionId: typeof parsed.sessionId === "string" ? parsed.sessionId : null,
        messages: Array.isArray(parsed.messages) ? parsed.messages : [],
      };
    } catch (_error) {
      return { sessionId: null, messages: [] };
    }
  }

  function persistSession() {
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          sessionId,
          messages: messageHistory.slice(-MAX_STORED_MESSAGES),
        }),
      );
    } catch (_error) {
      // A disabled storage API must not prevent the chat from working.
    }
  }

  function setLoading(active) {
    requestInFlight = active;
    loading.hidden = !active;
    input.disabled = active;
    sendButton.disabled = active;
    clearButton.disabled = active;
    for (const button of exampleButtons) button.disabled = active;
  }

  function initialMessage() {
    return {
      role: "assistant",
      text:
        "你好，我会把你的问题转换为受控分析计划，并只通过安全校验后的 Mock OpenSearch Query DSL 查询数据。",
      payload: {
        warnings: [
          dataSourceMode === "mock"
            ? "当前所有字段、状态码和结果均为 synthetic Mock 数据。"
            : "当前结果来自内网连接；请以已发布 Semantic Model 和指标版本为准。",
        ],
      },
    };
  }

  function appendMessage(message, { persist = true } = {}) {
    const fragment = template.content.cloneNode(true);
    const article = fragment.querySelector(".message");
    const label = fragment.querySelector(".message-label");
    const body = fragment.querySelector(".message-text");
    const payload = message.payload || {};
    const isUser = message.role === "user";
    const isError = ["error", "blocked", "not_answerable"].includes(payload.status);

    article.classList.add(isUser ? "message--user" : "message--assistant");
    if (isError) article.classList.add("message--error");
    if (payload.status === "needs_clarification") {
      article.classList.add("message--clarification");
    }
    label.textContent = isUser ? "You" : "ChatBI";
    body.textContent = message.text;

    if (!isUser) {
      renderKpis(fragment, payload.kpis || []);
      renderMetric(fragment, payload.metric_definition);
      renderChart(fragment, payload.chart);
      renderTable(fragment, payload.table);
      renderWarnings(fragment, payload.warnings || []);
      renderEvidence(fragment, payload.evidence);
    }

    conversation.append(fragment);
    conversation.scrollTop = conversation.scrollHeight;
    if (persist) {
      messageHistory.push(message);
      messageHistory = messageHistory.slice(-MAX_STORED_MESSAGES);
      persistSession();
    }
  }

  function renderKpis(fragment, kpis) {
    if (!kpis.length) return;
    const container = fragment.querySelector(".kpi-grid");
    container.hidden = false;
    for (const kpi of kpis) {
      const card = document.createElement("div");
      card.className = "kpi-card";
      const label = document.createElement("span");
      const value = document.createElement("strong");
      label.textContent = kpi.label;
      value.textContent = kpi.display_value;
      card.append(label, value);
      container.append(card);
    }
  }

  function renderMetric(fragment, metric) {
    if (!metric) return;
    const container = fragment.querySelector(".metric-note");
    container.hidden = false;
    const label = document.createElement("span");
    label.textContent = "当前指标口径";
    const text = document.createElement("p");
    text.textContent = `${metric.metric_id} · ${metric.metric_version} · ${metric.status}`;
    container.append(label, text);
  }

  function renderTable(fragment, table) {
    if (!table?.columns?.length || !table?.rows?.length) return;
    const section = fragment.querySelector(".table-section");
    const headRow = document.createElement("tr");
    const body = section.querySelector("tbody");
    for (const column of table.columns) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = column.label;
      headRow.append(cell);
    }
    for (const row of table.rows) {
      const tableRow = document.createElement("tr");
      for (const column of table.columns) {
        const cell = document.createElement("td");
        const value = row[column.field];
        cell.textContent = formatValue(value, column.type);
        tableRow.append(cell);
      }
      body.append(tableRow);
    }
    section.querySelector("thead").append(headRow);
    section.hidden = false;
  }

  function formatValue(value, type) {
    if (value === null || value === undefined) return "—";
    if (type === "percent") return `${Number(value).toFixed(2)}%`;
    if (type === "integer") return Number(value).toLocaleString("zh-CN");
    return String(value);
  }

  function renderChart(fragment, chart) {
    if (!chart?.data?.length) return;
    const section = fragment.querySelector(".chart-section");
    const canvas = section.querySelector(".chart-canvas");
    canvas.id = `chart-${++chartSequence}`;
    canvas.setAttribute("aria-label", chart.title);
    section.hidden = false;
    if (!globalThis.echarts) {
      canvas.textContent = "图表组件未加载，数据表格仍可使用。";
      canvas.classList.add("chart-canvas--fallback");
      return;
    }

    requestAnimationFrame(() => {
      const instance = globalThis.echarts.init(canvas, null, { renderer: "canvas" });
      const categories = chart.data.map((row) => row[chart.x_field]);
      const values = chart.data.map((row) => row[chart.y_field]);
      const isLine = chart.type === "line";
      const isPercent = chart.y_field === "failure_rate";
      instance.setOption({
        animationDuration: 450,
        color: ["#087f73"],
        title: {
          text: chart.title,
          left: 4,
          textStyle: {
            color: "#102a2b",
            fontFamily: "Segoe UI, PingFang SC, Microsoft YaHei, sans-serif",
            fontSize: 15,
            fontWeight: 700,
          },
        },
        tooltip: {
          trigger: "axis",
          valueFormatter: (value) =>
            isPercent ? `${Number(value).toFixed(2)}%` : String(value),
        },
        grid: { left: 42, right: 20, top: 58, bottom: isLine ? 58 : 42 },
        xAxis: {
          type: "category",
          data: categories,
          boundaryGap: !isLine,
          axisLabel: { color: "#627677", rotate: categories.length > 12 ? 35 : 0 },
          axisLine: { lineStyle: { color: "#cbd6d0" } },
        },
        yAxis: {
          type: "value",
          axisLabel: {
            color: "#627677",
            formatter: isPercent ? "{value}%" : "{value}",
          },
          splitLine: { lineStyle: { color: "#e8eeea" } },
        },
        series: [
          {
            name: chart.title,
            type: isLine ? "line" : "bar",
            data: values,
            smooth: isLine,
            connectNulls: false,
            symbolSize: 6,
            areaStyle: isLine ? { color: "rgba(8,127,115,.08)" } : undefined,
            itemStyle: { borderRadius: isLine ? 0 : [5, 5, 0, 0] },
            barMaxWidth: 56,
          },
        ],
      });
      chartInstances.add(instance);
      const observer = new ResizeObserver(() => instance.resize());
      observer.observe(canvas);
      canvas.dataset.rendered = "true";
    });
  }

  function renderWarnings(fragment, warnings) {
    if (!warnings.length) return;
    const container = fragment.querySelector(".message-warnings");
    const heading = document.createElement("strong");
    heading.textContent = "限制与提示";
    container.append(heading);
    for (const warning of warnings) {
      const item = document.createElement("p");
      item.textContent = warning;
      container.append(item);
    }
  }

  function renderEvidence(fragment, evidence) {
    if (!evidence || !Object.keys(evidence).length) return;
    const container = fragment.querySelector(".evidence");
    const content = container.querySelector(".evidence-content");
    const sections = [
      ["Analysis Plan", evidence.analysis_plan],
      ["Field Resolution", evidence.field_resolution],
      ["Query Plan", evidence.query_plan],
      [
        "Tool Selection",
        {
          tool: evidence.tool,
          reason_code: evidence.tool_reason_code,
        },
      ],
      ["OpenSearch Query DSL", evidence.query_dsl],
      ["Result Summary", evidence.raw_result_summary],
      ["Final Chart Data", evidence.chart_data],
      ["Data QA", evidence.qa],
    ];
    for (const [title, value] of sections) {
      if (value === null || value === undefined) continue;
      const section = document.createElement("section");
      const heading = document.createElement("h3");
      const pre = document.createElement("pre");
      heading.textContent = title;
      pre.textContent = JSON.stringify(value, null, 2);
      section.append(heading, pre);
      content.append(section);
    }
    container.hidden = false;
  }

  async function sendMessage(message) {
    if (requestInFlight) return;
    appendMessage({ role: "user", text: message });
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
      });
      const payload = await response.json();
      sessionId = payload.session_id || sessionId;
      appendMessage({
        role: "assistant",
        text: payload.assistant_message || "请求未返回可显示内容。",
        payload,
      });
    } catch (_error) {
      appendMessage({
        role: "assistant",
        text: "当前无法连接后端，请稍后重试。",
        payload: { status: "error" },
      });
    } finally {
      setLoading(false);
      input.focus();
    }
  }

  function disposeCharts() {
    for (const instance of chartInstances) instance.dispose();
    chartInstances.clear();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    void sendMessage(message);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  for (const button of exampleButtons) {
    button.addEventListener("click", () => {
      input.value = button.textContent.replace(/^\s*\d{2}\s*/, "").trim();
      input.focus();
    });
  }

  clearButton.addEventListener("click", async () => {
    if (requestInFlight) return;
    setLoading(true);
    try {
      await fetch("/api/session/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      sessionId = createSessionId();
      messageHistory = [];
      disposeCharts();
      conversation.replaceChildren();
      appendMessage({
        role: "assistant",
        text: "当前会话已清空。你可以开始一个新问题。",
        payload: {},
      });
    } catch (_error) {
      appendMessage({
        role: "assistant",
        text: "会话重置失败，请稍后重试。",
        payload: { status: "error" },
      });
    } finally {
      setLoading(false);
      input.focus();
    }
  });

  if (messageHistory.length) {
    const saved = [...messageHistory];
    messageHistory = [];
    for (const message of saved) appendMessage(message, { persist: false });
    messageHistory = saved;
  } else {
    appendMessage(initialMessage());
  }
})();
