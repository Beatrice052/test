import { useMemo, useState } from "react";
import type { AssistantCard, FormField, UseCaseCandidate } from "./api/types";
import { useIntakeStore } from "./state/intakeStore";

const moduleOrder = ["business", "audience", "channel", "compliance"];
const moduleShort: Record<string, string> = { business: "Biz", audience: "Aud", channel: "Ch", compliance: "Com" };

function statusClass(status: string) {
  if (status === "Confirmed") return "pill primary";
  if (status === "Missing Required") return "pill danger";
  if (status === "Needs Confirmation") return "pill warning";
  if (status === "AI Prefilled" || status === "Reference Prefilled") return "pill success";
  return "pill neutral";
}

function AssistantBubble({
  card,
  onAnswer,
  onApplyPreview,
  onReferenceChoice
}: {
  card: AssistantCard;
  onAnswer: (questionId: string, answer: string) => void;
  onApplyPreview: (previewId: string) => void;
  onReferenceChoice: (value: string) => void;
}) {
  if (card.type === "summary" || card.type === "finding") {
    return (
      <div className="guide-row bot">
        <div className="avatar bot">BOT</div>
        <div className={`bubble ${card.type === "finding" ? "action" : "bot"}`}>
          <div className="bubble-title">{card.title}</div>
          <div className="bubble-text">{card.body}</div>
        </div>
      </div>
    );
  }

  if (card.type === "question") {
    return (
      <div className="guide-row bot">
        <div className="avatar bot">BOT</div>
        <div className="bubble bot">
          <div className="bubble-title">{card.title}</div>
          <div className="bubble-text">{card.question}</div>
          {card.options && (
            <div className="quick-replies">
              {card.options.map((option) => (
                <button
                  className="quick-reply"
                  key={option.value}
                  type="button"
                  onClick={() => {
                    if (card.question_id === "q_reference_choice") onReferenceChoice(option.value);
                    else onAnswer(card.question_id, option.label);
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (card.type === "action_preview") {
    return (
      <div className="guide-row bot">
        <div className="avatar bot">BOT</div>
        <div className="bubble action">
          <div className="bubble-title">Action Preview</div>
          <div className="bubble-subtle">The following updates will be applied after confirmation:</div>
          <ul className="action-list">
            {card.action_preview.user_facing_updates.map((update) => (
              <li key={update.field_name}>{update.display_name}: {update.old_value} -&gt; {update.new_value}</li>
            ))}
          </ul>
          <div className="action-footer">
            <button className="btn primary small" type="button" onClick={() => onApplyPreview(card.action_preview.preview_id)}>
              Confirm and apply
            </button>
            <button className="btn secondary small" type="button">Edit before applying</button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default function App() {
  const {
    state,
    analyzeRequirement,
    buildFromChoice,
    resetIntake,
    answerQuestion,
    applyPreview,
    updateField,
    validate,
    exportForAc
  } = useIntakeStore();
  const [activeModule, setActiveModule] = useState("business");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [showAllFields, setShowAllFields] = useState(false);
  const [requirementDraft, setRequirementDraft] = useState("");

  const modules = state.modules;
  const moduleList = useMemo(() => moduleOrder.map((key) => modules[key]).filter(Boolean), [modules]);
  const currentModule = modules[activeModule] ?? moduleList[0];
  const allFields = Object.values(modules).flatMap((module) => module.fields);
  const visibleFields = (currentModule?.fields ?? []).filter((field) =>
    showAllFields ? true : !field.hidden && field.status !== "Not Applicable"
  );
  const missingCount = allFields.filter((field) => field.status === "Missing Required" && !field.hidden).length;
  const latestQuestion = [...state.assistantCards].reverse().find((card) => card.type === "question");
  const acSummary = `Use case summary: ${fieldValue(allFields, "use_case_name") || "pending"} - LOB ${fieldValue(allFields, "line_of_business") || "pending"} - Channel ${fieldValue(allFields, "channel") || "pending"}`;

  function chooseReference(value: string) {
    if (value === "CREATE_NEW") void buildFromChoice("CREATE_NEW");
    else void buildFromChoice("EDIT_REFERENCE", value);
  }

  function submitRequirement() {
    if (!requirementDraft.trim()) return;
    void analyzeRequirement(requirementDraft.trim());
    setRequirementDraft("");
  }

  function sendAssistantText(textarea: HTMLTextAreaElement | null | undefined) {
    const value = textarea?.value.trim();
    if (value && latestQuestion?.type === "question") {
      answerQuestion(latestQuestion.question_id, value);
      if (textarea) textarea.value = "";
    }
  }

  function commitField(field: FormField) {
    const value = draftValues[field.name] ?? field.value;
    if (value !== field.value) updateField(field.name, value);
  }

  return (
    <div>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">M</div>
          <div>
            <div className="brand-title">MDC Requirement Intake</div>
            <div className="brand-subtitle">Use Case Details</div>
          </div>
        </div>
        <div className="topbar-right">
          <span>{state.intakeId}</span>
          <span>{state.phase === "idle" ? "NEW INTAKE" : state.phase === "analyzed" ? "REFERENCE SELECTION" : state.mode.replace("_", " ")}</span>
          <span>{state.phase === "idle" ? "Waiting for requirement" : missingCount ? "Needs Input" : "Ready"}</span>
          {state.phase !== "idle" && <button className="btn small" type="button" onClick={resetIntake}>New intake</button>}
        </div>
      </header>

      <main className="page">
        <section className="card requirement-card">
          <div className="card-header">
            <div>
              <h2>Requirement</h2>
              <p>{state.phase === "idle" ? "Describe the requirement. Nothing is prefilled until you submit it." : "The assistant extracted signals from this requirement."}</p>
            </div>
          </div>
          <div className="card-body">
            {state.phase === "idle" ? (
              <div className="empty-intake">
                <h3>Start from a business requirement</h3>
                <p>Enter the business scenario in the Assistant. The backend will extract fields, retrieve candidate use cases, then let you choose the path.</p>
              </div>
            ) : (
              <>
                <div className="requirement-text large">{state.requirement}</div>
                <div className="insight-grid">
                  <div className="insight"><strong>124</strong><span>Detected department</span></div>
                  <div className="insight"><strong>{state.extractedSignals.channel ?? "Pending"}</strong><span>Detected channel</span></div>
                  <div className="insight"><strong>{state.extractedSignals.lob ?? "Pending"}</strong><span>Likely line of business</span></div>
                  <div className="insight"><strong>{state.candidates.length}</strong><span>Use case candidates</span></div>
                </div>
              </>
            )}
          </div>
        </section>

        <div className={`main-layout ${state.phase === "idle" ? "onboarding-layout" : ""}`}>
          <div>
            {state.phase === "analyzed" && (
              <CandidateSelection candidates={state.candidates} onChoose={chooseReference} />
            )}
            {state.phase === "draft" && (
              <>
                <CandidateSelection candidates={state.candidates} selectedId={state.selectedReference?.id} onChoose={chooseReference} />
                <section className="card form-card">
                  <div className="reference-bar">
                    <div className="reference-main">
                      <div className="reference-icon">{state.selectedReference ? "R" : "N"}</div>
                      <div>
                        <div className="reference-title">
                          {state.selectedReference ? `Reference use case: ${state.selectedReference.name}` : "Brand-new use case"}
                        </div>
                        <div className="reference-meta">
                          {state.selectedReference
                            ? `use_case_id: ${state.selectedReference.id} - source_system: ${state.selectedReference.source_system} - channel: ${state.selectedReference.channel}`
                            : "No historical values are inherited. Values come from requirement extraction and user input."}
                        </div>
                      </div>
                    </div>
                    <div className="reference-actions">
                      <button className="btn secondary" type="button" onClick={() => resetIntake()}>Change requirement</button>
                      <button className="btn secondary" type="button" onClick={() => void buildFromChoice("CREATE_NEW")}>Start new use case</button>
                    </div>
                  </div>

                  <div className={`form-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`}>
                    <aside className="module-sidebar">
                      <div className="sidebar-top">
                        <span className="sidebar-title">Modules</span>
                        <button className="collapse-btn" type="button" onClick={() => setSidebarCollapsed((value) => !value)}>{"<"}</button>
                      </div>
                      {moduleList.map((module) => {
                        const count = module.fields.filter((field) => ["Missing Required", "Needs Confirmation"].includes(field.status) && !field.hidden).length;
                        return (
                          <button className={`module-item ${module.id === (currentModule?.id ?? activeModule) ? "active" : ""}`} key={module.id} type="button" onClick={() => setActiveModule(module.id)}>
                            <span className="module-label">{module.title}</span>
                            <span className="module-short">{moduleShort[module.id] ?? module.title.slice(0, 3)}</span>
                            <span className="module-count">{count}</span>
                          </button>
                        );
                      })}
                    </aside>

                    <section className="form-area">
                      <div className="form-toolbar">
                        <div>
                          <h3>{currentModule?.title ?? "Loading"}</h3>
                          <p>{moduleSubtitle(currentModule?.id)}</p>
                        </div>
                        <div className="toolbar-actions">
                          <button className="btn secondary" type="button" onClick={() => setShowAllFields((value) => !value)}>
                            {showAllFields ? "Hide hidden fields" : "Show all fields"}
                          </button>
                          <button className="btn primary" type="button" onClick={validate}>Validate module</button>
                        </div>
                      </div>

                      <div className="form-table-wrap">
                        <table className="form-table">
                          <thead>
                            <tr><th className="col-field">Field</th><th className="col-value">Value</th><th className="col-help">Help</th><th className="col-status">Status</th><th className="col-action">Action</th></tr>
                          </thead>
                          <tbody>
                            {visibleFields.map((field) => (
                              <tr key={field.name}>
                                <td><div className="field-name">{field.displayName}</div></td>
                                <td>
                                  <FieldValueControl
                                    field={field}
                                    value={draftValues[field.name] ?? field.value}
                                    onChange={(value) => setDraftValues((current) => ({ ...current, [field.name]: value }))}
                                    onCommit={() => commitField(field)}
                                  />
                                </td>
                                <td><button className="help-icon" title={field.help} type="button">?</button></td>
                                <td><span className={statusClass(field.status)}>{field.status}</span></td>
                                <td><button className="btn small" type="button" onClick={() => commitField(field)}>{field.status === "Confirmed" ? "Edit" : "Confirm"}</button></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="form-footer">
                        <span>{missingCount ? `${missingCount} field${missingCount > 1 ? "s" : ""} need attention.` : "No urgent field in this module."}</span>
                        <div className="footer-actions">
                          <button className="btn secondary" type="button">Save draft</button>
                          <button className="btn primary" type="button" onClick={exportForAc} disabled={!state.validation?.ready_for_ac}>Continue to AC input</button>
                        </div>
                      </div>
                      <div className="ac-preview">
                        <div className="ac-preview-title">AC generation input preview</div>
                        <div className="ac-preview-box">
                          <b>{acSummary}</b><br />
                          Trigger: {fieldValue(allFields, "message_trigger_conditions") || state.extractedSignals.trigger || "pending"}<br />
                          Missing: {missingCount} required field(s) still need input.
                        </div>
                      </div>
                    </section>
                  </div>
                </section>
              </>
            )}
          </div>

          <aside className="assistant-panel card">
            <div className="card-header compact">
              <div>
                <h2>Assistant</h2>
                <p>Follow the guided conversation to complete this use case.</p>
              </div>
            </div>
            <div className="assistant-body">
              <div className="guided-thread">
                <div className="guide-row bot">
                  <div className="avatar bot">BOT</div>
                  <div className="bubble bot">
                    <div className="bubble-text">Welcome to MDC portal. I am the copilot assistant. Describe the requirement and I will guide you to complete the use case intake.</div>
                  </div>
                </div>
                {state.phase !== "idle" && (
                  <div className="guide-row user">
                    <div className="bubble user"><div className="bubble-title">User</div><div className="bubble-text">{state.requirement}</div></div>
                    <div className="avatar user">ME</div>
                  </div>
                )}
                {state.assistantCards.map((card, index) => (
                  <AssistantBubble key={`${card.type}-${index}`} card={card} onAnswer={answerQuestion} onApplyPreview={applyPreview} onReferenceChoice={chooseReference} />
                ))}
              </div>
            </div>
            <div className="assistant-input">
              <textarea
                key={state.phase === "idle" ? "requirement-start" : "assistant-reply"}
                value={state.phase === "idle" ? requirementDraft : undefined}
                onChange={(event) => { if (state.phase === "idle") setRequirementDraft(event.target.value); }}
                placeholder={state.phase === "idle" ? "Describe the requirement..." : state.phase === "analyzed" ? "Choose a reference candidate or create a new use case." : "Reply to the Assistant..."}
                disabled={state.loading || state.phase === "analyzed"}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    if (state.phase === "idle") submitRequirement();
                    else if (state.phase === "draft") sendAssistantText(event.currentTarget);
                  }
                }}
              />
              <div className="assistant-actions">
                {state.phase === "idle" ? (
                  <>
                    <button className="btn primary" type="button" onClick={submitRequirement} disabled={state.loading || !requirementDraft.trim()}>Analyze requirement</button>
                    <button className="btn secondary" type="button" onClick={() => setRequirementDraft("We have a new business scenario about investment shopping cart. When customers add investment products into the HASE mobile app cart and the products are close to expiry, the system should trigger a message. The message should be sent to the customer's mobile phone based on the customer's language preference.")}>Use sample</button>
                  </>
                ) : state.phase === "analyzed" ? (
                  <>
                    <button className="btn primary" type="button" onClick={() => state.candidates[0] && chooseReference(state.candidates[0].id)}>Use best match</button>
                    <button className="btn secondary" type="button" onClick={() => chooseReference("CREATE_NEW")}>Create new</button>
                  </>
                ) : (
                  <>
                    <button className="btn primary" type="button" onClick={(event) => sendAssistantText(event.currentTarget.closest(".assistant-input")?.querySelector("textarea"))}>Send</button>
                    <button className="btn secondary" type="button" onClick={validate}>Show missing fields</button>
                  </>
                )}
              </div>
            </div>
          </aside>
        </div>

        {state.toast && <div className="selection-toast show">{state.toast}</div>}
      </main>
    </div>
  );
}

function CandidateSelection({
  candidates,
  selectedId,
  onChoose
}: {
  candidates: UseCaseCandidate[];
  selectedId?: string;
  onChoose: (value: string) => void;
}) {
  return (
    <section className="card candidates-card">
      <div className="card-header">
        <div>
          <h2>Related historical use cases</h2>
          <p>The backend retrieved similar use cases. Choose one as reference, or create a brand-new use case.</p>
        </div>
        <button className="btn secondary" type="button" onClick={() => onChoose("CREATE_NEW")}>Start new use case</button>
      </div>
      <div className="card-body">
        <div className="candidate-grid">
          {candidates.map((candidate) => (
            <article className={`candidate-card ${selectedId === candidate.id ? "selected" : ""}`} key={candidate.id}>
              <div className="candidate-top">
                <span className={`pill ${candidate.badge === "Best match" ? "success" : "neutral"}`}>{candidate.badge}</span>
                <span className="pill primary">Similarity {candidate.similarity}</span>
              </div>
              <h3 className="candidate-title">{candidate.name}</h3>
              <div className="candidate-meta">
                Project: {candidate.project}<br />
                use_case_id: {candidate.id} - source_system: {candidate.source_system} - LOB: {candidate.lob} - channel: {candidate.channel}
              </div>
              <div className="candidate-reason">{candidate.reason}</div>
              <div className="candidate-actions">
                <button className="btn primary small" type="button" onClick={() => onChoose(candidate.id)}>
                  {selectedId === candidate.id ? "Selected as reference" : "Use as reference"}
                </button>
                <button className="btn secondary small" type="button">View details</button>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function FieldValueControl({
  field,
  value,
  onChange,
  onCommit
}: {
  field: FormField;
  value: string;
  onChange: (value: string) => void;
  onCommit: () => void;
}) {
  const options = field.options ?? [];
  if (options.length) {
    const hasCurrentValue = value && !options.some((option) => option.value === value);
    return (
      <select
        className="value-control"
        value={hasCurrentValue ? "__custom__" : value}
        title={options.find((option) => option.value === value)?.description}
        onChange={(event) => {
          if (event.target.value === "__custom__") return;
          onChange(event.target.value);
        }}
        onBlur={onCommit}
      >
        <option value="">Select value</option>
        {hasCurrentValue && <option value="__custom__">{value}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value} title={option.description}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }
  return (
    <input
      className="value-control"
      value={value}
      placeholder="Add value"
      onChange={(event) => onChange(event.target.value)}
      onBlur={onCommit}
    />
  );
}

function fieldValue(fields: FormField[], name: string) {
  return fields.find((field) => field.name === name)?.value ?? "";
}

function moduleSubtitle(moduleId?: string) {
  if (moduleId === "business") return "Confirm basic use case information, source system, and ownership.";
  if (moduleId === "audience") return "Confirm customer audience, trigger logic, and eligibility rules.";
  if (moduleId === "channel") return "Confirm message channel, sender setup, and customer-facing content fields.";
  if (moduleId === "compliance") return "Confirm consent basis, compliance review, and launch readiness.";
  return "Review and complete user-facing fields.";
}
