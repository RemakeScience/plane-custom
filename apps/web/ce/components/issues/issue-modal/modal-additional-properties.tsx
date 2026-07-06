/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect } from "react";
import { observer } from "mobx-react";
import { useFormContext } from "react-hook-form";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EIssuePropertyType } from "@plane/types";
import type { TIssueProperty, TIssuePropertyOption, TIssuePropertyValue } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
// components
import type { TIssueFields } from "@/plane-web/components/issues/issue-modal";
import { PropertyRelationField } from "@/plane-web/components/issues/property-fields/relation-field";
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

/** Compute the declared default value(s) of a property (mirrors the backend). */
const getPropertyDefaultValue = (property: TIssueProperty, options: TIssuePropertyOption[]): TIssuePropertyValue[] => {
  let values: TIssuePropertyValue[];
  if (property.property_type === EIssuePropertyType.OPTION) {
    values = options.filter((option) => option.is_default && option.is_active).map((option) => option.id);
  } else {
    values = (property.default_value ?? []).filter((value) => value !== null && value !== "");
  }
  return property.is_multi ? values : values.slice(0, 1);
};

/** Renders a single custom property input bound to the modal's value state. */
const PropertyField = observer(function PropertyField(props: {
  property: TIssueProperty;
  value: TIssuePropertyValue[];
  error: string | undefined;
  projectId: string;
  workspaceSlug: string;
  onChange: (value: TIssuePropertyValue[]) => void;
}) {
  const { property, value, error, projectId, workspaceSlug, onChange } = props;
  const { getPropertyOptions } = useIssueProperties();
  const { t } = useTranslation();
  const single = value?.[0];

  const renderInput = () => {
    switch (property.property_type) {
      case EIssuePropertyType.RELATION:
        return (
          <PropertyRelationField
            property={property}
            value={value}
            projectId={projectId}
            workspaceSlug={workspaceSlug}
            onChange={onChange}
          />
        );
      case EIssuePropertyType.FILE:
        return (
          <input
            type="url"
            placeholder={t("work_item_types.settings.properties.ce.file_placeholder")}
            className={inputClassName}
            value={typeof single === "string" ? single : ""}
            onChange={(e) => onChange(e.target.value === "" ? [] : [e.target.value])}
          />
        );
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
            <option value="">{t("work_item_types.settings.properties.ce.select_placeholder")}</option>
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
  const { getTypeProperties, fetchProjectProperties, getPropertyOptions } = useIssueProperties();
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
  const propertyIdsKey = properties.map((property) => property.id).join(",");

  // When creating (no existing work item), pre-fill each property with its
  // declared default so the user sees it and it flows through the normal save.
  useEffect(() => {
    if (workItemId || !typeId || properties.length === 0) return;
    setIssuePropertyValues((prev) => {
      let changed = false;
      const next = { ...prev };
      properties.forEach((property) => {
        if (next[property.id]?.length) return;
        const defaults = getPropertyDefaultValue(property, getPropertyOptions(property.id));
        if (defaults.length > 0) {
          next[property.id] = defaults;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyIdsKey, typeId, workItemId]);

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
          projectId={projectId ?? ""}
          workspaceSlug={workspaceSlug}
          onChange={(value) => setIssuePropertyValues((prev) => ({ ...prev, [property.id]: value }))}
        />
      ))}
    </div>
  );
});
