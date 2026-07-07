/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane types
import type { TIssueServiceType, TWorkItemWidgets } from "@plane/types";
// components
// [FORK] github-pr-integration — CE extension seam renders the Pull Requests widget
import { GithubPullRequestsCollapsible } from "@/components/issues/issue-detail-widgets/pull-requests";

export type TWorkItemAdditionalWidgetCollapsiblesProps = {
  disabled: boolean;
  hideWidgets: TWorkItemWidgets[];
  issueServiceType: TIssueServiceType;
  projectId: string;
  workItemId: string;
  workspaceSlug: string;
};

export function WorkItemAdditionalWidgetCollapsibles(props: TWorkItemAdditionalWidgetCollapsiblesProps) {
  const { hideWidgets, issueServiceType, projectId, workItemId, workspaceSlug } = props;

  if (hideWidgets?.includes("pull-requests")) return null;

  return (
    <GithubPullRequestsCollapsible
      workspaceSlug={workspaceSlug}
      projectId={projectId}
      issueId={workItemId}
      issueServiceType={issueServiceType}
    />
  );
}
