/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useFormContext } from "react-hook-form";
import useSWR from "swr";
// plane imports
import { EIssuePropertyType } from "@plane/types";
import type { TIssueProperty, TIssuePropertyValue } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
// components
import type { TIssueFields } from "@/plane-web/components/issues/issue-modal";
// hooks
import { useIssueModal } from "@/hooks/context/use-issue-modal";
import { useIssueProperties } from "@/hooks/store/use-issue-properties";
// services
import { IssuePropertyValueService } from "@/services/issue-property-value.service";

const issuePropertyValueService = new IssuePropertyValueService();

export type TWorkItemModalAdditionalPropertiesProps = {
  isDraft?: boolean;
  projectId: string | null;
  workItemId: string | undefined;
  workspaceSlug: string;
};

const inputClassName =
  "h-8 w-full rounded border border-subtle-1 bg-layer-2 px-2 text-13 text-primary outline-none focus:border-accent-primary";

/** Renders a single custom property input bound to the modal's value state. */
const PropertyField = observer(function PropertyField(props: {
  property: TIssueProperty;
  value: TIssuePropertyValue[];
  error: string | undefined;
  onChange: (value: TIssuePropertyValue[]) => void;
}) {
  const { property, value, error, onChange } = props;
  const { getPropertyOptions } = useIssueProperties();
  const single = value?.[0];

  const renderInput = () => {
    switch (property.property_type) {
      case EIssuePropertyType.BOOLEAN:
        return <ToggleSwitch value={single === true || single === "true"} onChange={(v) => onChange([v])} size="sm" />;
      case EIssuePropertyType.DECIMAL:
        return (
          <input
            type="number"
            className={inputClassName}
            value={single != null ? String(single) : ""}
            onChange={(e) => onChange(e.target.value === "" ? [] : [e.target.value])}
          />
        );
      case EIssuePropertyType.DATETIME:
        return (
          <input
            type="date"
            className={inputClassName}
            value={typeof single === "string" ? single.slice(0, 10) : ""}
            onChange={(e) => onChange(e.target.value === "" ? [] : [e.target.value])}
          />
        );
      case EIssuePropertyType.OPTION: {
        const options = getPropertyOptions(property.id);
        if (property.is_multi) {
          const selected = (value ?? []).map(String);
          return (
            <select
              multiple
              className="min-h-16 w-full rounded border border-subtle-1 bg-layer-2 px-2 py-1 text-13 text-primary"
              value={selected}
              onChange={(e) => onChange(Array.from(e.target.selectedOptions).map((o) => o.value))}
            >
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          );
        }
        return (
          <select
            className={inputClassName}
            value={typeof single === "string" ? single : ""}
            onChange={(e) => onChange(e.target.value === "" ? [] : [e.target.value])}
          >
            <option value="">Select…</option>
            {options.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
              </option>
            ))}
          </select>
        );
      }
      default:
        return (
          <input
            type={
              property.property_type === EIssuePropertyType.EMAIL
                ? "email"
                : property.property_type === EIssuePropertyType.URL
                  ? "url"
                  : "text"
            }
            className={inputClassName}
            value={typeof single === "string" ? single : ""}
            onChange={(e) => onChange(e.target.value === "" ? [] : [e.target.value])}
          />
        );
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <span className="text-13 font-medium text-secondary">
        {property.display_name}
        {property.is_required && <span className="text-danger-strong"> *</span>}
      </span>
      {renderInput()}
      {error && <span className="text-danger-strong text-11">{error}</span>}
    </div>
  );
});

export const WorkItemModalAdditionalProperties = observer(function WorkItemModalAdditionalProperties(
  props: TWorkItemModalAdditionalPropertiesProps
) {
  const { projectId, workItemId, workspaceSlug } = props;
  const { watch } = useFormContext<TIssueFields>();
  const typeId = watch("type_id");
  const { getTypeProperties, fetchProjectProperties } = useIssueProperties();
  const { issuePropertyValues, setIssuePropertyValues, issuePropertyValueErrors } = useIssueModal();

  // Ensure the project's property definitions are loaded for the modal.
  useSWR(
    projectId ? `PROJECT_ISSUE_PROPERTIES_${projectId}` : null,
    async () => {
      if (projectId) await fetchProjectProperties(workspaceSlug, projectId);
    },
    { revalidateOnFocus: false, revalidateIfStale: false }
  );

  const properties = projectId && typeId ? (getTypeProperties(projectId, typeId, true) ?? []) : [];

  // Seed existing values when editing an existing work item.
  useSWR(
    workItemId && projectId ? `ISSUE_PROPERTY_VALUES_${workItemId}` : null,
    async () => {
      if (!workItemId || !projectId) return;
      const values = await issuePropertyValueService.fetch(workspaceSlug, projectId, workItemId);
      setIssuePropertyValues(values ?? {});
    },
    { revalidateOnFocus: false }
  );

  if (properties.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 px-4 py-3">
      {properties.map((property) => (
        <PropertyField
          key={property.id}
          property={property}
          value={issuePropertyValues[property.id] ?? []}
          error={issuePropertyValueErrors[property.id]}
          onChange={(value) => setIssuePropertyValues((prev) => ({ ...prev, [property.id]: value }))}
        />
      ))}
    </div>
  );
});
