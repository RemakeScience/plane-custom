/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import type { TIssueServiceType } from "@plane/types";
import { Collapsible } from "@plane/ui";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// local imports
import { GithubPullRequestsCollapsibleContent } from "./content";
import { GithubPullRequestsCollapsibleTitle } from "./title";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueServiceType: TIssueServiceType;
};

export const GithubPullRequestsCollapsible = observer(function GithubPullRequestsCollapsible(props: Props) {
  const { workspaceSlug, projectId, issueId, issueServiceType } = props;
  // store hooks
  const {
    openWidgets,
    toggleOpenWidget,
    githubPullRequest: { getPullRequestsByIssueId, fetchPullRequests },
  } = useIssueDetail(issueServiceType);

  // fetch the linked pull requests for this work item
  useSWR(
    workspaceSlug && projectId && issueId ? `GITHUB_PULL_REQUESTS_${workspaceSlug}_${projectId}_${issueId}` : null,
    workspaceSlug && projectId && issueId ? () => fetchPullRequests(workspaceSlug, projectId, issueId) : null
  );

  const count = getPullRequestsByIssueId(issueId)?.length ?? 0;
  // self-hide when there are no linked pull requests
  if (count === 0) return null;

  const isCollapsibleOpen = openWidgets.includes("pull-requests");

  return (
    <Collapsible
      isOpen={isCollapsibleOpen}
      onToggle={() => toggleOpenWidget("pull-requests")}
      title={
        <GithubPullRequestsCollapsibleTitle
          isOpen={isCollapsibleOpen}
          issueId={issueId}
          issueServiceType={issueServiceType}
        />
      }
      buttonClassName="w-full"
    >
      <GithubPullRequestsCollapsibleContent issueId={issueId} issueServiceType={issueServiceType} />
    </Collapsible>
  );
});
