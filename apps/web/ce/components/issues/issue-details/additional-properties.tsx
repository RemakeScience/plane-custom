/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types
import React, { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EIssuePropertyType } from "@plane/types";
import type { TIssueProperty, TIssuePropertyValue, TIssuePropertyValues } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
// components
import { FilePropertyField } from "@/plane-web/components/issues/property-fields/file-field";
import { PropertyRelationField } from "@/plane-web/components/issues/property-fields/relation-field";
// hooks
import { useIssueProperties } from "@/hooks/store/use-issue-properties";
// services
import { IssuePropertyValueService } from "@/services/issue-property-value.service";

const issuePropertyValueService = new IssuePropertyValueService();

export type TWorkItemAdditionalSidebarProperties = {
  workItemId: string;
  workItemTypeId: string | null;
  projectId: string;
  workspaceSlug: string;
  isEditable: boolean;
  isPeekView?: boolean;
};

const inputClassName =
  "h-8 w-full rounded border border-subtle-1 bg-layer-2 px-2 text-13 text-primary outline-none focus:border-accent-primary disabled:opacity-60";

/** Compact editable renderer for a single custom property value. */
const SidebarPropertyField = observer(function SidebarPropertyField(props: {
  property: TIssueProperty;
  value: TIssuePropertyValue[];
  isEditable: boolean;
  projectId: string;
  workspaceSlug: string;
  onCommit: (value: TIssuePropertyValue[]) => void;
}) {
  const { property, value, isEditable, projectId, workspaceSlug, onCommit } = props;
  const { getPropertyOptions } = useIssueProperties();
  const { t } = useTranslation();
  const single = value?.[0];

  switch (property.property_type) {
    case EIssuePropertyType.RELATION:
      return (
        <PropertyRelationField
          property={property}
          value={value}
          disabled={!isEditable}
          projectId={projectId}
          workspaceSlug={workspaceSlug}
          onChange={onCommit}
        />
      );
    case EIssuePropertyType.FILE:
      return (
        <FilePropertyField
          value={value}
          disabled={!isEditable}
          projectId={projectId}
          workspaceSlug={workspaceSlug}
          onChange={onCommit}
        />
      );
    case EIssuePropertyType.BOOLEAN:
      return (
        <ToggleSwitch
          value={single === true || single === "true"}
          onChange={(v) => onCommit([v])}
          size="sm"
          disabled={!isEditable}
        />
      );
    case EIssuePropertyType.OPTION: {
      const options = getPropertyOptions(property.id);
      return (
        <select
          className={inputClassName}
          disabled={!isEditable}
          value={typeof single === "string" ? single : ""}
          onChange={(e) => onCommit(e.target.value === "" ? [] : [e.target.value])}
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
    case EIssuePropertyType.DECIMAL:
    case EIssuePropertyType.DATETIME:
    case EIssuePropertyType.EMAIL:
    case EIssuePropertyType.URL:
    case EIssuePropertyType.FILE:
    default:
      return (
        <input
          type={
            property.property_type === EIssuePropertyType.DECIMAL
              ? "number"
              : property.property_type === EIssuePropertyType.DATETIME
                ? "date"
                : property.property_type === EIssuePropertyType.EMAIL
                  ? "email"
                  : property.property_type === EIssuePropertyType.URL ||
                      property.property_type === EIssuePropertyType.FILE
                    ? "url"
                    : "text"
          }
          className={inputClassName}
          disabled={!isEditable}
          defaultValue={
            typeof single === "string"
              ? property.property_type === EIssuePropertyType.DATETIME
                ? single.slice(0, 10)
                : single
              : ""
          }
          onBlur={(e) => onCommit(e.target.value === "" ? [] : [e.target.value])}
        />
      );
  }
});

/**
 * Renders a work item's custom property values in the detail/peek sidebar and
 * persists edits immediately (per property) via the value endpoint.
 */
export const WorkItemAdditionalSidebarProperties = observer(function WorkItemAdditionalSidebarProperties(
  props: TWorkItemAdditionalSidebarProperties
) {
  const { workItemId, workItemTypeId, projectId, workspaceSlug, isEditable } = props;
  const { getTypeProperties, fetchProjectProperties } = useIssueProperties();
  const [values, setValues] = useState<TIssuePropertyValues>({});

  useSWR(
    projectId ? `PROJECT_ISSUE_PROPERTIES_${projectId}` : null,
    async () => {
      if (projectId) await fetchProjectProperties(workspaceSlug, projectId);
    },
    { revalidateOnFocus: false, revalidateIfStale: false }
  );

  useSWR(
    workItemId && projectId ? `ISSUE_PROPERTY_VALUES_${workItemId}` : null,
    async () => {
      const fetched = await issuePropertyValueService.fetch(workspaceSlug, projectId, workItemId);
      setValues(fetched ?? {});
    },
    { revalidateOnFocus: false }
  );

  const properties = workItemTypeId ? (getTypeProperties(projectId, workItemTypeId, true) ?? []) : [];
  if (properties.length === 0) return null;

  const handleCommit = async (property: TIssueProperty, newValue: TIssuePropertyValue[]) => {
    setValues((prev) => ({ ...prev, [property.id]: newValue }));
    try {
      await issuePropertyValueService.upsert(workspaceSlug, projectId, workItemId, { [property.id]: newValue });
    } catch {
      // keep the optimistic value; the next fetch reconciles
    }
  };

  return (
    <div className="flex flex-col gap-3 py-2">
      {properties.map((property) => (
        <div key={property.id} className="flex items-center gap-2">
          <span className="w-2/5 flex-shrink-0 text-13 text-tertiary">
            {property.display_name}
            {property.is_required && <span className="text-danger-strong"> *</span>}
          </span>
          <div className="flex-1">
            <SidebarPropertyField
              property={property}
              value={values[property.id] ?? []}
              isEditable={isEditable}
              projectId={projectId}
              workspaceSlug={workspaceSlug}
              onCommit={(newValue) => handleCommit(property, newValue)}
            />
          </div>
        </div>
      ))}
    </div>
  );
});
