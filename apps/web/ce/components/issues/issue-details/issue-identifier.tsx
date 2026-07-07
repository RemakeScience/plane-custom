/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types
import { useEffect } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import type { TIssueIdentifierProps, TIssueTypeIdentifier } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useIssueTypes } from "@/hooks/store/use-issue-types";
import { useProject } from "@/hooks/store/use-project";
import { IdentifierText } from "@/components/issues/issue-detail/identifier-text";

// [FORK] work-item-types
const ICON_SIZE: Record<string, number> = { sm: 12, md: 14, lg: 16 };

export const IssueIdentifier = observer(function IssueIdentifier(props: TIssueIdentifierProps) {
  const { projectId, variant, size, displayProperties, enableClickToCopyIdentifier = false } = props;
  // [FORK] work-item-types
  // router
  const { workspaceSlug: routeWorkspaceSlug } = useParams();
  const workspaceSlug = routeWorkspaceSlug?.toString() ?? "";
  // store hooks
  const { getProjectIdentifierById } = useProject();
  // [FORK] work-item-types
  const { fetchProjectIssueTypes, getProjectIssueTypeIds, isIssueTypeEnabledForProject } = useIssueTypes();
  const {
    issue: { getIssueById },
  } = useIssueDetail();

  // [FORK] work-item-types
  // Lazily load the project's work item types the first time an identifier renders
  // for the project (the `fetchedMap` guard keeps this to a single request).
  const isIssueTypeEnabled = isIssueTypeEnabledForProject(projectId);
  const hasFetchedIssueTypes = getProjectIssueTypeIds(projectId) !== undefined;
  useEffect(() => {
    if (isIssueTypeEnabled && workspaceSlug && projectId && !hasFetchedIssueTypes) {
      void fetchProjectIssueTypes(workspaceSlug, projectId);
    }
  }, [isIssueTypeEnabled, workspaceSlug, projectId, hasFetchedIssueTypes, fetchProjectIssueTypes]);
  // Determine if the component is using store data or not
  const isUsingStoreData = "issueId" in props;
  // derived values
  const issue = isUsingStoreData ? getIssueById(props.issueId) : null;
  const projectIdentifier = isUsingStoreData ? getProjectIdentifierById(projectId) : props.projectIdentifier;
  const issueSequenceId = isUsingStoreData ? issue?.sequence_id : props.issueSequenceId;
  // [FORK] work-item-types
  const issueTypeId = isUsingStoreData ? issue?.type_id : props.issueTypeId;
  const shouldRenderIssueID = displayProperties ? displayProperties.key : true;
  const shouldRenderIssueTypeIcon = displayProperties ? displayProperties.issue_type : true;

  if (!shouldRenderIssueID && !shouldRenderIssueTypeIcon) return null;

  return (
    <div className="flex shrink-0 items-center space-x-2">
      {/* [FORK] work-item-types */}
      {shouldRenderIssueTypeIcon && issueTypeId && <IssueTypeIdentifier issueTypeId={issueTypeId} size={size} />}
      {shouldRenderIssueID && (
        <IdentifierText
          identifier={`${projectIdentifier}-${issueSequenceId}`}
          enableClickToCopyIdentifier={enableClickToCopyIdentifier}
          variant={variant}
          size={size}
        />
      )}
    </div>
  );
});

// [FORK] work-item-types
export const IssueTypeIdentifier = observer(function IssueTypeIdentifier(props: TIssueTypeIdentifier) {
  const { issueTypeId, size = "md" } = props;
  // store hooks
  const { getIssueTypeById } = useIssueTypes();
  // derived values
  const issueType = getIssueTypeById(issueTypeId);

  if (!issueType?.logo_props?.in_use) return null;

  return (
    <span className="flex shrink-0 items-center justify-center" title={issueType.name}>
      <Logo logo={issueType.logo_props} size={ICON_SIZE[size] ?? 14} />
    </span>
  );
});
