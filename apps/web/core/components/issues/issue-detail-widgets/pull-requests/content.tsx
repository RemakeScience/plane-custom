/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
// plane imports
import type { TIssueServiceType } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// local imports
import { GithubPullRequestDetail } from "./pull-request-detail";

type Props = {
  issueId: string;
  issueServiceType: TIssueServiceType;
};

export const GithubPullRequestsCollapsibleContent = observer(function GithubPullRequestsCollapsibleContent(
  props: Props
) {
  const { issueId, issueServiceType } = props;
  // store hooks
  const {
    githubPullRequest: { getPullRequestsByIssueId },
  } = useIssueDetail(issueServiceType);

  const prIds = getPullRequestsByIssueId(issueId) ?? [];

  return (
    <div className="flex flex-col gap-2">
      {prIds.map((prId) => (
        <GithubPullRequestDetail key={prId} prId={prId} issueServiceType={issueServiceType} />
      ))}
    </div>
  );
});
