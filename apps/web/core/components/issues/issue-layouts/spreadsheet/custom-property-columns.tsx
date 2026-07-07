/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { useTranslation } from "@plane/i18n";
import { EIssuePropertyType, EIssuePropertyRelationType } from "@plane/types";
import type { TIssueProperty, TIssuePropertyValue } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
// components
import { FilePropertyField } from "@/plane-web/components/issues/property-fields/file-field";
// hooks
import { useIssueProperties } from "@/hooks/store/use-issue-properties";
import { useMember } from "@/hooks/store/use-member";
// services
import { IssuePropertyValueService } from "@/services/issue-property-value.service";

const issuePropertyValueService = new IssuePropertyValueService();

const headerClassName =
  "h-11 min-w-36 whitespace-nowrap border-r-[0.5px] border-subtle bg-layer-1 px-4 text-left text-13 font-medium text-tertiary";
const cellClassName =
  "h-11 min-w-36 border-r-[1px] border-subtle px-2 text-13 text-secondary after:absolute after:bottom-[-1px] after:w-full after:border after:border-subtle";
const inputClassName =
  "h-8 w-full rounded border border-transparent bg-transparent px-1 text-13 text-secondary outline-none hover:border-subtle-1 focus:border-accent-primary disabled:hover:border-transparent";

/** Active custom properties of a project, sorted deterministically so the header
 * and body cells always render the same columns in the same order. */
const useProjectCustomProperties = (projectId: string | undefined): TIssueProperty[] => {
  const { getProjectPropertyIds, getPropertyById, fetchProjectProperties } = useIssueProperties();
  const { workspaceSlug } = useParams();

  useSWR(
    projectId && workspaceSlug ? `PROJECT_ISSUE_PROPERTIES_${projectId}` : null,
    async () => {
      if (projectId && workspaceSlug) await fetchProjectProperties(workspaceSlug.toString(), projectId);
    },
    { revalidateOnFocus: false, revalidateIfStale: false }
  );

  const propertyIds = getProjectPropertyIds(projectId);
  return useMemo(() => {
    if (!propertyIds) return [];
    // `.filter()` already returns a fresh array, so sorting it in place is safe.
    return propertyIds
      .map((id) => getPropertyById(id))
      .filter((property): property is TIssueProperty => Boolean(property) && !!property?.is_active)
      .sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
  }, [propertyIds, getPropertyById]);
};

/** Header cells for each active custom property of the current project. Also
 * triggers a single bulk fetch of every visible work item's values, avoiding an
 * N+1 per-row request. */
export const SpreadsheetCustomPropertyHeaders = observer(function SpreadsheetCustomPropertyHeaders(props: {
  issueIds?: string[];
}) {
  const { issueIds } = props;
  const { projectId, workspaceSlug } = useParams();
  const properties = useProjectCustomProperties(projectId?.toString());
  const { fetchBulkValues } = useIssueProperties();

  const issueIdsKey = (issueIds ?? []).join(",");
  useSWR(
    projectId && workspaceSlug && properties.length > 0 && issueIdsKey
      ? `BULK_PROPERTY_VALUES_${projectId}_${issueIdsKey}`
      : null,
    async () => {
      if (projectId && workspaceSlug && issueIds) {
        await fetchBulkValues(workspaceSlug.toString(), projectId.toString(), issueIds);
      }
    },
    { revalidateOnFocus: false }
  );

  return (
    <>
      {properties.map((property) => (
        <th key={property.id} className={headerClassName} tabIndex={-1}>
          {property.display_name}
        </th>
      ))}
    </>
  );
});

/** Read-only display of a RELATION value (edited from the modal/sidebar). */
const RelationValueDisplay = observer(function RelationValueDisplay(props: {
  property: TIssueProperty;
  scalars: TIssuePropertyValue[];
}) {
  const { property, scalars } = props;
  const { getUserDetails } = useMember();
  if (property.relation_type === EIssuePropertyRelationType.MEMBER) {
    const names = scalars.map((value) => getUserDetails(String(value))?.display_name ?? String(value).slice(0, 8));
    return <span className="truncate px-1">{names.join(", ")}</span>;
  }
  return <span className="truncate px-1">{scalars.map((value) => String(value).slice(0, 8)).join(", ")}</span>;
});

/** Editable renderer for a single custom property value inside a spreadsheet cell. */
const CustomPropertyCell = observer(function CustomPropertyCell(props: {
  property: TIssueProperty;
  values: TIssuePropertyValue[];
  disabled: boolean;
  projectId: string;
  workspaceSlug: string;
  onCommit: (value: TIssuePropertyValue[]) => void;
}) {
  const { property, values, disabled, projectId, workspaceSlug, onCommit } = props;
  const { getPropertyOptions } = useIssueProperties();
  const { t } = useTranslation();
  const single = values?.[0];

  switch (property.property_type) {
    case EIssuePropertyType.FILE:
      return (
        <FilePropertyField
          value={values}
          disabled={disabled}
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
          disabled={disabled}
        />
      );
    case EIssuePropertyType.OPTION: {
      const options = getPropertyOptions(property.id);
      return (
        <select
          className={inputClassName}
          disabled={disabled}
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
    case EIssuePropertyType.RELATION:
      return <RelationValueDisplay property={property} scalars={values} />;
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
          disabled={disabled}
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

/** Body cells rendering each active custom property's value for one work item. */
export const SpreadsheetCustomPropertyValueCells = observer(function SpreadsheetCustomPropertyValueCells(props: {
  issueId: string;
  disabled?: boolean;
}) {
  const { issueId, disabled = false } = props;
  const { projectId, workspaceSlug } = useParams();
  const projectIdStr = projectId?.toString();
  const properties = useProjectCustomProperties(projectIdStr);
  const { getIssueValues, setIssueValues } = useIssueProperties();

  const values = getIssueValues(issueId);

  const handleCommit = async (property: TIssueProperty, newValue: TIssuePropertyValue[]) => {
    if (!projectIdStr || !workspaceSlug) return;
    const previous = getIssueValues(issueId) ?? {};
    setIssueValues(issueId, { ...previous, [property.id]: newValue });
    try {
      const refreshed = await issuePropertyValueService.upsert(workspaceSlug.toString(), projectIdStr, issueId, {
        [property.id]: newValue,
      });
      setIssueValues(issueId, refreshed ?? {});
    } catch {
      setIssueValues(issueId, previous);
    }
  };

  return (
    <>
      {properties.map((property) => (
        <td key={property.id} tabIndex={0} className={cellClassName}>
          <div className="flex h-full items-center overflow-hidden">
            <CustomPropertyCell
              property={property}
              values={values?.[property.id] ?? []}
              disabled={disabled}
              projectId={projectIdStr ?? ""}
              workspaceSlug={workspaceSlug?.toString() ?? ""}
              onCommit={(newValue) => handleCommit(property, newValue)}
            />
          </div>
        </td>
      ))}
    </>
  );
});
