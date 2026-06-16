const demoState = {
  requirement:
    "We have a new business scenario about investment shopping cart. When customers add investment products into the HASE mobile app cart and the products are close to expiry, the system should trigger a message. The message should be sent to the customer’s mobile phone based on the customer’s language preference.",
  extractedSignals: {
    department: "124",
    topChannel: "SMS",
    lob: "WPB",
    matchedChannels: [
      { channel: "SMS", count: 3 },
      { channel: "Email", count: 2 },
      { channel: "Mobile Push", count: 1 }
    ]
  },
  candidates: [
    {
      id: "M1004",
      name: "RDP 004",
      project: "ICCM Migration",
      source_system: "PEGA",
      lob: "WPB",
      similarity: 0.86,
      badge: "Best match",
      reason:
        "Similar investment-related messaging scenario with SMS as the historical sending mode."
    },
    {
      id: "M1011",
      name: "RDP 011",
      project: "Digital Campaign",
      source_system: "CMS",
      lob: "WPB",
      similarity: 0.72,
      badge: "Candidate",
      reason:
        "Relevant customer language preference and campaign notification patterns."
    }
  ],
  selectedReference: {
    id: "M1004",
    name: "RDP 004",
    project: "ICCM Migration",
    source_system: "PEGA",
    lob: "WPB",
    similarity: 0.86
  },
  mode: "EDIT_REFERENCE",
  modules: {
    business: {
      title: "Business Context",
      subtitle: "Confirm basic use case information, source system, and ownership.",
      fields: [
        {
          name: "Use Case Name",
          field_name: "use_case_name",
          type: "text",
          value: "Investment cart expiry reminder",
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "A business-readable name used for search, approval, and reuse.",
          hint: "This value was generated from the requirement."
        },
        {
          name: "Line of Business",
          field_name: "line_of_business",
          type: "select",
          value: "WPB",
          options: ["WPB", "RBWM", "Cards", "Loans", "Insurance"],
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "The business line that owns this messaging use case.",
          hint: "The system inferred WPB based on the selected reference and investment-related context."
        },
        {
          name: "Source System",
          field_name: "source_system",
          type: "select",
          value: "PEGA",
          options: ["PEGA", "CMS", "HASE mobile app", "CRM", "Other"],
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "The system that provides customer data or triggers the message.",
          hint: "This can be inherited from a selected reference use case or edited by the user."
        }
      ]
    },
    audience: {
      title: "Audience & Trigger",
      subtitle: "Define target audience, trigger scenario, and required data source.",
      fields: [
        {
          name: "Target Customer Segment",
          field_name: "target_customer_segment",
          type: "textarea",
          value:
            "Customers with investment products in the HASE mobile app cart that are close to expiry",
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "The customer group that should receive this message.",
          hint: "This value was extracted from the original requirement."
        },
        {
          name: "Trigger Scenario",
          field_name: "trigger_scenario",
          type: "textarea",
          value: "Investment product in cart is close to expiry",
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "The business event or condition that triggers the message.",
          hint: "This was extracted from the requirement and can be edited if the actual trigger is different."
        },
        {
          name: "Product Expiry Data Source",
          field_name: "expiry_data_source",
          type: "select",
          value: "",
          options: ["", "PEGA", "HASE mobile app", "CMS", "CRM", "Not sure"],
          status: "Missing Required",
          statusType: "danger",
          action: "Edit",
          help:
            "The system or data source used to determine whether the investment product is close to expiry.",
          hint: "This is needed to complete the detailed trigger logic."
        }
      ]
    },
    channel: {
      title: "Channel & Content",
      subtitle: "Confirm delivery channel and content-related settings.",
      fields: [
        {
          name: "Channel Setup",
          field_name: "channel_setup",
          type: "select",
          value: "SMS",
          options: ["SMS", "Mobile Push", "SMS + Mobile Push", "Email", "SMS + Email"],
          status: "Needs Confirmation",
          statusType: "warning",
          action: "Confirm",
          help: "The channel or channel combination used to deliver the message.",
          hint:
            "SMS is recommended based on department history, but the HASE mobile app context may indicate Mobile Push."
        },
        {
          name: "Customer Language Preference",
          field_name: "customer_language_preference",
          type: "select",
          value: "Use customer preferred language",
          options: ["Use customer preferred language", "English only", "Chinese only", "Bilingual"],
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "The language rule used when sending the message.",
          hint: "The requirement says the message should follow the customer's language preference."
        },
        {
          name: "Message Template",
          field_name: "template_id",
          type: "text",
          value: "",
          status: "Optional",
          statusType: "neutral",
          action: "Edit",
          help: "The message template to be used.",
          hint: "This can be selected later after the use case is confirmed."
        }
      ]
    },
    compliance: {
      title: "Compliance & Launch",
      subtitle: "Confirm message purpose, approval requirements, and launch readiness.",
      fields: [
        {
          name: "Message Purpose",
          field_name: "message_purpose",
          type: "select",
          value: "Service reminder",
          options: ["Service reminder", "Marketing message", "Operational notice", "Not sure"],
          status: "AI Prefilled",
          statusType: "success",
          action: "Edit",
          help: "The business purpose of the message.",
          hint: "The system currently treats this as a service reminder because it is triggered by product expiry."
        },
        {
          name: "Approval Owner",
          field_name: "approval_owner",
          type: "text",
          value: "",
          status: "Optional",
          statusType: "neutral",
          action: "Edit",
          help: "The person or team responsible for approving the use case.",
          hint: "This can be completed later if not needed for AC generation."
        }
      ]
    }
  }
};

const moduleOrder = ["business", "audience", "channel", "compliance"];
let currentModule = "business";
let assistantThreadState = "initial";
let latestActionPreview = null;

const $ = (id) => document.getElementById(id);

function init() {
  $("requirementText").textContent = demoState.requirement;
  $("detectedDept").textContent = demoState.extractedSignals.department;
  $("topChannel").textContent = demoState.extractedSignals.topChannel;
  $("detectedLob").textContent = demoState.extractedSignals.lob;
  $("candidateCount").textContent = demoState.candidates.length;

  renderCandidateCards();
  renderReference();
  renderModule("business");
  renderAssistant("details");
  updateAcPreview();

  bindStaticEvents();
}

function bindStaticEvents() {
  document.querySelectorAll(".module-item").forEach(item => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".module-item").forEach(el => el.classList.remove("active"));
      item.classList.add("active");
      renderModule(item.dataset.module);
    });
  });

  $("toggleSidebar").addEventListener("click", () => {
    $("formShell").classList.toggle("sidebar-collapsed");
  });

  $("startNewTop").addEventListener("click", startNewUseCase);
  $("startNewUseCase").addEventListener("click", startNewUseCase);
  $("changeReference").addEventListener("click", () => {
    $("candidateSection").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  $("closeHelp").addEventListener("click", closeHelp);
  $("helpModal").addEventListener("click", event => {
    if (event.target === $("helpModal")) closeHelp();
  });

  $("sendAssistant").addEventListener("click", () => {
    const input = $("assistantInput");
    const text = input.value.trim();
    if (text) {
      appendUserAndPreview(text);
      input.value = "";
    }
  });

  $("showMissing").addEventListener("click", () => {
    renderAssistant("details");
  });
}

function renderCandidateCards() {
  $("candidateGrid").innerHTML = demoState.candidates.map(candidate => {
    const selected = demoState.selectedReference && demoState.selectedReference.id === candidate.id;
    return `
      <article class="candidate-card ${selected ? "selected" : ""}">
        <div class="candidate-top">
          <span class="pill ${candidate.badge === "Best match" ? "success" : "neutral"}">${candidate.badge}</span>
          <span class="pill primary">Similarity ${candidate.similarity}</span>
        </div>
        <h3 class="candidate-title">${candidate.name}</h3>
        <div class="candidate-meta">
          Project: ${candidate.project}<br />
          use_case_id: ${candidate.id} · source_system: ${candidate.source_system} · LOB: ${candidate.lob}
        </div>
        <div class="candidate-reason">${candidate.reason}</div>
        <div class="candidate-actions">
          <button class="btn primary select-reference" data-id="${candidate.id}">${selected ? "Selected as reference" : "Use as reference"}</button>
          <button class="btn secondary confirm-directly" data-id="${candidate.id}">Confirm directly</button>
          <button class="btn secondary">View details</button>
        </div>
      </article>
    `;
  }).join("");

  document.querySelectorAll(".select-reference").forEach(button => {
    button.addEventListener("click", () => selectReference(button.dataset.id, "EDIT_REFERENCE"));
  });

  document.querySelectorAll(".confirm-directly").forEach(button => {
    button.addEventListener("click", () => selectReference(button.dataset.id, "CONFIRM_DIRECTLY"));
  });
}

function selectReference(candidateId, mode) {
  const candidate = demoState.candidates.find(item => item.id === candidateId);
  demoState.selectedReference = candidate;
  demoState.mode = mode;

  $("referenceProgress").classList.remove("active");
  $("referenceProgress").classList.add("done");
  $("referenceProgress").textContent = "Reference selected";
  $("detailsProgress").classList.add("active");

  renderCandidateCards();
  renderReference();
  renderModule(currentModule);
  renderAssistant(mode === "CONFIRM_DIRECTLY" ? "confirmed" : "details");
  updateAcPreview();
}

function startNewUseCase() {
  demoState.selectedReference = null;
  demoState.mode = "CREATE_NEW";

  $("referenceProgress").classList.remove("active");
  $("referenceProgress").classList.add("done");
  $("referenceProgress").textContent = "New use case";
  $("detailsProgress").classList.add("active");

  const sourceSystem = demoState.modules.business.fields.find(f => f.field_name === "source_system");
  sourceSystem.value = "";
  sourceSystem.status = "Missing Required";
  sourceSystem.statusType = "danger";

  const channel = demoState.modules.channel.fields.find(f => f.field_name === "channel_setup");
  channel.value = "";
  channel.status = "Missing Required";
  channel.statusType = "danger";
  channel.action = "Edit";

  renderCandidateCards();
  renderReference();
  renderModule(currentModule);
  renderAssistant("new");
  updateAcPreview();
}

function renderReference() {
  if (!demoState.selectedReference) {
    $("referenceTitle").textContent = "Brand-new use case";
    $("referenceMeta").textContent = "No historical field values are inherited. Values come from the requirement and user input.";
    $("referenceIcon").textContent = "N";
    $("headerSubtitle").textContent = "Brand-new use case · Complete use case details before AC generation";
    return;
  }

  const candidate = demoState.selectedReference;
  $("referenceTitle").textContent = demoState.mode === "CONFIRM_DIRECTLY"
    ? `Confirmed reference use case: ${candidate.name}`
    : `Reference use case: ${candidate.name}`;
  $("referenceMeta").textContent = `use_case_id: ${candidate.id} · source_system: ${candidate.source_system} · LOB: ${candidate.lob} · similarity ${candidate.similarity}`;
  $("referenceIcon").textContent = candidate.name.split(" ")[0].slice(0, 1);
  $("headerSubtitle").textContent = `${candidate.name} selected · Complete use case details before AC generation`;
}

function renderAssistant(context) {
  const selected = demoState.selectedReference;
  const referenceText = selected
    ? `${selected.name} (${selected.id})`
    : "a brand-new use case";

  $("assistantBody").innerHTML = `
    <div class="guided-thread" id="guidedThread">
      ${renderBotBubble("Welcome", "Welcome to MDC portal. I am the copilot assistant. Describe the requirement and I will guide you to complete the use case intake.")}
      ${renderUserBubble("I want to send wealth product related messages. Please help me create the use case based on similar historical cases if applicable.")}
      ${renderBotBubble(
        "Requirement understood",
        "I understood this as a WPB wealth product messaging use case. I detected department 124, likely LOB WPB, and historical channel usage led by SMS."
      )}
      ${renderBotBubble(
        "Reference recommendation",
        `I recommend using ${referenceText} as the reference. You can use it as a base, confirm it directly, or start a new use case if it is not suitable.`
      )}
      ${renderQuestionBubble()}
      ${latestActionPreview ? renderActionPreviewBubble(latestActionPreview) : ""}
      ${renderFieldExplanationBubble()}
    </div>
  `;

  bindAssistantControls();
}

function renderBotBubble(title, text) {
  return `
    <div class="guide-row bot">
      <div class="avatar bot">BOT</div>
      <div class="bubble bot">
        <div class="bubble-title">${title}</div>
        <div class="bubble-text">${text}</div>
      </div>
    </div>
  `;
}

function renderUserBubble(text) {
  return `
    <div class="guide-row user">
      <div class="bubble user">
        <div class="bubble-title">User</div>
        <div class="bubble-text">${text}</div>
      </div>
      <div class="avatar user">ME</div>
    </div>
  `;
}

function renderQuestionBubble() {
  return `
    <div class="guide-row bot">
      <div class="avatar bot">BOT</div>
      <div class="bubble bot">
        <div class="bubble-title">Questions</div>
        <ol class="question-list">
          <li>Who is the target customer segment?</li>
          <li>Is this a service reminder or a marketing message?</li>
          <li>Should the channel remain SMS, change to Email, change to Mobile Push, or use multiple channels?</li>
        </ol>
        <div class="quick-replies">
          <button class="quick-reply" data-quick="wealth_email">Wealth customers · Email only</button>
          <button class="quick-reply" data-quick="wealth_sms">Wealth customers · SMS</button>
          <button class="quick-reply" data-quick="mobile_push">Use Mobile Push</button>
          <button class="quick-reply" data-quick="service_reminder">Service reminder</button>
        </div>
      </div>
    </div>
  `;
}

function renderActionPreviewBubble(preview) {
  const items = preview.updates.map(update => `<li>${update.label} → ${update.value}</li>`).join("");
  return `
    <div class="guide-row bot">
      <div class="avatar bot">BOT</div>
      <div class="bubble action">
        <div class="bubble-title">Action Preview</div>
        <div class="bubble-subtle">The following updates will be applied after confirmation:</div>
        <ul class="action-list">${items}</ul>
        <div class="action-footer">
          <button class="btn primary small" id="confirmAssistantPreview">Confirm and apply</button>
          <button class="btn secondary small" id="editAssistantPreview">Edit before applying</button>
        </div>
      </div>
    </div>
  `;
}

function renderFieldExplanationBubble() {
  return `
    <div class="guide-row bot">
      <div class="avatar bot">BOT</div>
      <div class="bubble explain">
        <div class="bubble-title">Field Explanation</div>
        <div class="bubble-subtle">
          <b>Trigger Scenario</b> describes the business event that starts the message, such as product maturity, cart abandonment, or a scheduled campaign.
        </div>
        <span class="explain-link" data-module-jump="audience">Open Audience & Trigger module</span>
      </div>
    </div>
  `;
}

function renderQuestionCards() {
  return "";
}

function renderModule(moduleKey) {
  currentModule = moduleKey;
  const module = demoState.modules[moduleKey];
  $("moduleTitle").textContent = module.title;
  $("moduleSubtitle").textContent = module.subtitle;

  const needAttention = module.fields.filter(field =>
    field.status === "Missing Required" || field.status === "Needs Confirmation"
  ).length;

  $("moduleFooter").textContent = needAttention > 0
    ? `${needAttention} field${needAttention > 1 ? "s" : ""} in this module need attention.`
    : "No urgent field in this module.";

  $("fieldTableBody").innerHTML = module.fields.map((field, index) => `
    <tr>
      <td><div class="field-name">${field.name}</div></td>
      <td>${renderValueControl(field)}</td>
      <td><button class="help-icon" data-index="${index}" title="Explain ${field.name}">?</button></td>
      <td><span class="${statusClass(field.statusType)}">${field.status}</span></td>
      <td>
        <div class="action-cell">
          <button class="btn small row-action" data-index="${index}">${field.action}</button>
        </div>
      </td>
    </tr>
  `).join("");

  document.querySelectorAll(".help-icon").forEach(button => {
    button.addEventListener("click", () => {
      const field = demoState.modules[currentModule].fields[Number(button.dataset.index)];
      openHelp(field);
    });
  });

  document.querySelectorAll(".row-action").forEach(button => {
    button.addEventListener("click", () => {
      const field = demoState.modules[currentModule].fields[Number(button.dataset.index)];
      if (field.status === "Needs Confirmation") {
        field.status = "Confirmed";
        field.statusType = "primary";
        field.action = "Edit";
        renderModule(currentModule);
        updateModuleCounts();
        updateAcPreview();
      }
    });
  });

  document.querySelectorAll(".value-control").forEach(control => {
    control.addEventListener("change", () => {
      const fieldName = control.dataset.field;
      const field = Object.values(demoState.modules)
        .flatMap(module => module.fields)
        .find(item => item.field_name === fieldName);
      if (field) {
        field.value = control.value;
        if (field.status === "Missing Required" && control.value) {
          field.status = "AI Prefilled";
          field.statusType = "success";
        }
        updateModuleCounts();
        updateAcPreview();
      }
    });
  });

  updateModuleCounts();
  updateAcPreview();
}

function renderValueControl(field) {
  if (field.type === "select") {
    const options = field.options.map(option => {
      const value = option === "" ? "" : option;
      const label = option === "" ? "Select value" : option;
      const selected = field.value === option ? "selected" : "";
      return `<option value="${value}" ${selected}>${label}</option>`;
    }).join("");
    return `<select class="value-control" data-field="${field.field_name}">${options}</select>`;
  }

  if (field.type === "textarea") {
    return `<textarea class="value-control" data-field="${field.field_name}">${field.value || ""}</textarea>`;
  }

  return `<input class="value-control" data-field="${field.field_name}" value="${field.value || ""}" />`;
}

function statusClass(type) {
  if (type === "success") return "pill success";
  if (type === "warning") return "pill warning";
  if (type === "danger") return "pill danger";
  if (type === "primary") return "pill primary";
  return "pill neutral";
}

function updateModuleCounts() {
  moduleOrder.forEach(key => {
    const count = demoState.modules[key].fields.filter(field =>
      field.status === "Missing Required" || field.status === "Needs Confirmation"
    ).length;
    $(`count-${key}`).textContent = count;
  });
}

function updateAcPreview() {
  const values = Object.values(demoState.modules).flatMap(module => module.fields);
  const getValue = fieldName => {
    const field = values.find(item => item.field_name === fieldName);
    return field && field.value ? field.value : "pending";
  };

  $("acPreview").innerHTML = `
    <b>Use case summary:</b> ${getValue("use_case_name")} · LOB ${getValue("line_of_business")} · Channel ${getValue("channel_setup")}<br/>
    <b>Trigger:</b> ${getValue("trigger_scenario")}<br/>
    <b>Audience:</b> ${getValue("target_customer_segment")}<br/>
    <b>Missing:</b> ${values.filter(field => field.status === "Missing Required").length} required field(s) still need input.
  `;
}

function openHelp(field) {
  $("helpTitle").textContent = field.name;
  $("helpDescription").textContent = field.help;
  $("helpHint").textContent = field.hint;
  $("helpModal").style.display = "flex";
}

function closeHelp() {
  $("helpModal").style.display = "none";
}

function bindChoices() {
  document.querySelectorAll(".choice").forEach(choice => {
    choice.onclick = () => {
      const answer = choice.dataset.answer;

      if (answer === "SMS" || answer === "Mobile Push" || answer === "Both") {
        const channel = demoState.modules.channel.fields.find(f => f.field_name === "channel_setup");
        channel.value = answer === "Both" ? "SMS + Mobile Push" : answer;
        channel.status = "Confirmed";
        channel.statusType = "primary";
        channel.action = "Edit";
      }

      if (answer === "PEGA" || answer === "HASE mobile app" || answer === "Not sure") {
        const source = demoState.modules.audience.fields.find(f => f.field_name === "expiry_data_source");
        source.value = answer;
        source.status = answer === "Not sure" ? "Needs Confirmation" : "AI Prefilled";
        source.statusType = answer === "Not sure" ? "warning" : "success";
        source.action = "Edit";
      }

      if (answer === "Service reminder" || answer === "Marketing") {
        const purpose = demoState.modules.compliance.fields.find(f => f.field_name === "message_purpose");
        purpose.value = answer === "Marketing" ? "Marketing message" : "Service reminder";
        purpose.status = "AI Prefilled";
        purpose.statusType = "success";
      }

      renderModule(currentModule);
      renderAssistant("details");
      showToast(`Updated: ${answer}`);
    };
  });
}


function getFieldByName(fieldName) {
  return Object.values(demoState.modules)
    .flatMap(module => module.fields)
    .find(item => item.field_name === fieldName);
}

function showToast(message) {
  let toast = document.getElementById("selectionToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "selectionToast";
    toast.className = "selection-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2400);
}

function buildPreviewFromUserText(text) {
  const lower = text.toLowerCase();
  const channel = lower.includes("email")
    ? "Email"
    : lower.includes("push")
      ? "Mobile Push"
      : lower.includes("both")
        ? "SMS + Mobile Push"
        : "SMS";

  const segment = lower.includes("mature") || lower.includes("maturity")
    ? "Customers holding wealth products that will mature soon"
    : "Customers interested in wealth products";

  const purpose = lower.includes("marketing")
    ? "Marketing message"
    : "Service reminder";

  return {
    rawText: text,
    updates: [
      { field: "target_customer_segment", label: "Target Customer Segment", value: segment },
      { field: "channel_setup", label: "Channel Setup", value: channel },
      { field: "message_purpose", label: "Message Purpose", value: purpose },
      { field: "trigger_scenario", label: "Trigger Scenario", value: "Product maturity event trigger" }
    ]
  };
}

function applyActionPreview(preview) {
  preview.updates.forEach(update => {
    const field = getFieldByName(update.field);
    if (!field) return;
    field.value = update.value;
    field.status = update.field === "channel_setup" ? "Confirmed" : "AI Prefilled";
    field.statusType = update.field === "channel_setup" ? "primary" : "success";
    field.action = "Edit";
  });

  const expirySource = getFieldByName("expiry_data_source");
  if (expirySource && !expirySource.value) {
    expirySource.value = "Not sure";
    expirySource.status = "Needs Confirmation";
    expirySource.statusType = "warning";
    expirySource.action = "Edit";
  }

  renderModule(currentModule);
  updateAcPreview();
  showToast("Action preview applied to the use case form.");
}

function appendUserAndPreview(text) {
  latestActionPreview = buildPreviewFromUserText(text);
  const thread = document.getElementById("guidedThread");
  if (!thread) return;

  const explanation = document.querySelector(".bubble.explain")?.closest(".guide-row");
  if (explanation) explanation.remove();

  thread.insertAdjacentHTML("beforeend", renderUserBubble(text));
  thread.insertAdjacentHTML("beforeend", renderActionPreviewBubble(latestActionPreview));
  thread.insertAdjacentHTML("beforeend", renderFieldExplanationBubble());
  bindAssistantControls();
  thread.scrollTop = thread.scrollHeight;
}

function bindAssistantControls() {
  document.querySelectorAll(".quick-reply").forEach(button => {
    button.onclick = () => {
      const type = button.dataset.quick;
      const textByType = {
        wealth_email: "The target customers are customers holding wealth products that will mature soon. Send email only.",
        wealth_sms: "The target customers are customers holding wealth products that will mature soon. Keep SMS as the channel.",
        mobile_push: "Use Mobile Push because this scenario is related to HASE mobile app.",
        service_reminder: "This is a service reminder, not a marketing message."
      };
      const text = textByType[type] || button.textContent;
      appendUserAndPreview(text);
    };
  });

  const confirmBtn = document.getElementById("confirmAssistantPreview");
  if (confirmBtn) {
    confirmBtn.onclick = () => {
      if (latestActionPreview) {
        applyActionPreview(latestActionPreview);
      }
    };
  }

  const editBtn = document.getElementById("editAssistantPreview");
  if (editBtn) {
    editBtn.onclick = () => showToast("In the connected version, users can edit the action preview before applying.");
  }

  document.querySelectorAll("[data-module-jump]").forEach(link => {
    link.onclick = () => {
      const moduleKey = link.dataset.moduleJump;
      const item = document.querySelector(`.module-item[data-module="${moduleKey}"]`);
      if (item) {
        document.querySelectorAll(".module-item").forEach(el => el.classList.remove("active"));
        item.classList.add("active");
        renderModule(moduleKey);
      }
    };
  });
}


document.addEventListener("DOMContentLoaded", init);
