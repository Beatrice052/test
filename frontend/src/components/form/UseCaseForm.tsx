import { useMemo, useState } from "react";
import type { FormField, FormModule } from "../../api/types";
import { FieldHelpModal } from "./FieldHelpModal";
import { FieldRow } from "./FieldRow";
import { ModuleSidebar } from "./ModuleSidebar";

type Props = {
  modules: Record<string, FormModule>;
  onUpdateField: (fieldName: string, value: string) => void;
};

export function UseCaseForm({ modules, onUpdateField }: Props) {
  const moduleList = useMemo(() => Object.values(modules), [modules]);
  const [activeModule, setActiveModule] = useState(moduleList[0]?.id ?? "business");
  const [helpField, setHelpField] = useState<FormField | undefined>();
  const currentModule = moduleList.find((module) => module.id === activeModule) ?? moduleList[0];

  if (!currentModule) {
    return <section className="workspace-card empty-state">Loading form modules...</section>;
  }

  const visibleFields = currentModule.fields.filter((field) => !field.hidden && field.status !== "Not Applicable");
  const hiddenFields = currentModule.fields.filter((field) => field.hidden || field.status === "Not Applicable");

  return (
    <section className="workspace-card form-workspace">
      <div className="workspace-header">
        <div>
          <p className="eyebrow">Use Case Form</p>
          <h2>{currentModule.title}</h2>
        </div>
        <span className="completion">{currentModule.complete} / {currentModule.total} complete</span>
      </div>
      <div className="form-grid">
        <ModuleSidebar modules={moduleList} activeModule={currentModule.id} onSelect={setActiveModule} />
        <div className="field-list">
          {visibleFields.map((field) => (
            <FieldRow key={field.name} field={field} onHelp={setHelpField} onUpdate={onUpdateField} />
          ))}
          {hiddenFields.length > 0 && (
            <details className="hidden-fields">
              <summary>Hidden by current setup ({hiddenFields.length})</summary>
              <p>Dependent fields are not part of the business review until the selected setup makes them relevant.</p>
            </details>
          )}
        </div>
      </div>
      <FieldHelpModal field={helpField} onClose={() => setHelpField(undefined)} />
    </section>
  );
}
