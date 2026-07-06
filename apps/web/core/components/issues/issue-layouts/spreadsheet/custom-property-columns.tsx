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
import type { TIssueProperty, TIssuePropertyValue, TIssuePropertyValues } from "@plane/types";
// hooks
import { useIssueProperties } from "@/hooks/store/use-issue-properties";
import { useMember } from "@/hooks/store/use-member";
// services
import { IssuePropertyValueService } from "@/services/issue-property-value.service";

const issuePropertyValueService = new IssuePropertyValueService();

const headerClassName =
  "h-11 min-w-36 whitespace-nowrap border-r-[0.5px] border-subtle bg-layer-1 px-4 text-left text-13 font-medium text-tertiary";
const cellClassName =
  "h-11 min-w-36 border-r-[1px] border-subtle px-4 text-13 text-secondary after:absolute after:bottom-[-1px] after:w-full after:border after:border-subtle";

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

/** Header cells for each active custom property of the current project. */
export const SpreadsheetCustomPropertyHeaders = observer(function SpreadsheetCustomPropertyHeaders() {
  const { projectId } = useParams();
  const properties = useProjectCustomProperties(projectId?.toString());

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

/** Read-only display of a single property's stored value(s). */
const PropertyValueDisplay = observer(function PropertyValueDisplay(props: {
  property: TIssueProperty;
  values: TIssuePropertyValue[];
}) {
  const { property, values } = props;
  const { getPropertyOptions } = useIssueProperties();
  const { getUserDetails } = useMember();
  const { t } = useTranslation();
  const scalars = values.filter((value) => value !== null && value !== undefined && value !== "");

  if (scalars.length === 0) return <span className="text-placeholder">—</span>;

  switch (property.property_type) {
    case EIssuePropertyType.BOOLEAN:
      return (
        <span>
          {scalars[0] === true || scalars[0] === "true"
            ? t("work_item_types.settings.properties.ce.value.yes")
            : t("work_item_types.settings.properties.ce.value.no")}
        </span>
      );
    case EIssuePropertyType.DATETIME:
      return <span>{typeof scalars[0] === "string" ? scalars[0].slice(0, 10) : String(scalars[0])}</span>;
    case EIssuePropertyType.OPTION: {
      const options = getPropertyOptions(property.id);
      const labels = scalars.map((value) => options.find((option) => option.id === value)?.name ?? String(value));
      return <span className="truncate">{labels.join(", ")}</span>;
    }
    case EIssuePropertyType.RELATION: {
      if (property.relation_type === EIssuePropertyRelationType.MEMBER) {
        const names = scalars.map((value) => getUserDetails(String(value))?.display_name ?? String(value).slice(0, 8));
        return <span className="truncate">{names.join(", ")}</span>;
      }
      return <span className="truncate">{scalars.map((value) => String(value).slice(0, 8)).join(", ")}</span>;
    }
    case EIssuePropertyType.URL:
    case EIssuePropertyType.EMAIL:
    case EIssuePropertyType.FILE:
      return (
        <a
          href={property.property_type === EIssuePropertyType.EMAIL ? `mailto:${scalars[0]}` : String(scalars[0])}
          target="_blank"
          rel="noopener noreferrer"
          className="truncate text-accent-primary hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {String(scalars[0])}
        </a>
      );
    default:
      return <span className="truncate">{scalars.map(String).join(", ")}</span>;
  }
});

/** Body cells rendering each active custom property's value for one work item. */
export const SpreadsheetCustomPropertyValueCells = observer(function SpreadsheetCustomPropertyValueCells(props: {
  issueId: string;
}) {
  const { issueId } = props;
  const { projectId, workspaceSlug } = useParams();
  const projectIdStr = projectId?.toString();
  const properties = useProjectCustomProperties(projectIdStr);

  const { data: values } = useSWR<TIssuePropertyValues>(
    issueId && projectIdStr && workspaceSlug && properties.length > 0 ? `ISSUE_PROPERTY_VALUES_${issueId}` : null,
    () => issuePropertyValueService.fetch(workspaceSlug!.toString(), projectIdStr!, issueId),
    { revalidateOnFocus: false }
  );

  return (
    <>
      {properties.map((property) => (
        <td key={property.id} tabIndex={0} className={cellClassName}>
          <div className="flex h-full items-center overflow-hidden">
            <PropertyValueDisplay property={property} values={values?.[property.id] ?? []} />
          </div>
        </td>
      ))}
    </>
  );
});
