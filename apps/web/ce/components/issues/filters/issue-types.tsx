/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
// components
import { FilterHeader, FilterOption } from "@/components/issues/issue-layouts/filters";
// hooks
import { useIssueTypes } from "@/hooks/store/use-issue-types";

type Props = {
  appliedFilters: string[] | null;
  handleUpdate: (val: string) => void;
  searchQuery: string;
};

export const FilterIssueTypes = observer(function FilterIssueTypes(props: Props) {
  const { appliedFilters, handleUpdate, searchQuery } = props;
  // router
  const { workspaceSlug: routeWorkspaceSlug, projectId: routeProjectId } = useParams();
  const workspaceSlug = routeWorkspaceSlug?.toString() ?? "";
  const projectId = routeProjectId?.toString() ?? "";
  // store
  const { fetchProjectIssueTypes, getProjectIssueTypes, getProjectIssueTypeIds, isIssueTypeEnabledForProject } =
    useIssueTypes();
  // states
  const [previewEnabled, setPreviewEnabled] = useState(true);
  // derived values
  const isEnabled = isIssueTypeEnabledForProject(projectId);
  const hasFetched = getProjectIssueTypeIds(projectId) !== undefined;

  useEffect(() => {
    if (isEnabled && workspaceSlug && projectId && !hasFetched) {
      void fetchProjectIssueTypes(workspaceSlug, projectId);
    }
  }, [isEnabled, workspaceSlug, projectId, hasFetched, fetchProjectIssueTypes]);

  if (!isEnabled) return null;

  const appliedFiltersCount = appliedFilters?.length ?? 0;
  const options = (getProjectIssueTypes(projectId, true) ?? []).filter((issueType) =>
    issueType.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <FilterHeader
        title={`Work item type${appliedFiltersCount > 0 ? ` (${appliedFiltersCount})` : ""}`}
        isPreviewEnabled={previewEnabled}
        handleIsPreviewEnabled={() => setPreviewEnabled(!previewEnabled)}
      />
      {previewEnabled && (
        <div>
          {options.length > 0 ? (
            options.map((issueType) => (
              <FilterOption
                key={issueType.id}
                isChecked={appliedFilters?.includes(issueType.id) ?? false}
                onClick={() => handleUpdate(issueType.id)}
                icon={issueType.logo_props?.in_use ? <Logo logo={issueType.logo_props} size={12} /> : undefined}
                title={issueType.name}
              />
            ))
          ) : (
            <p className="text-11 text-placeholder italic">No matches found</p>
          )}
        </div>
      )}
    </>
  );
});
