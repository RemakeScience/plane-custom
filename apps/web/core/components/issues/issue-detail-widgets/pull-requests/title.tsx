/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useMemo } from "react";
import { observer } from "mobx-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TIssueServiceType } from "@plane/types";
import { CollapsibleButton } from "@plane/ui";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";

type Props = {
  isOpen: boolean;
  issueId: string;
  issueServiceType: TIssueServiceType;
};

export const GithubPullRequestsCollapsibleTitle = observer(function GithubPullRequestsCollapsibleTitle(props: Props) {
  const { isOpen, issueId, issueServiceType } = props;
  // translation
  const { t } = useTranslation();
  // store hooks
  const {
    githubPullRequest: { getPullRequestsByIssueId },
  } = useIssueDetail(issueServiceType);

  const count = getPullRequestsByIssueId(issueId)?.length ?? 0;

  const indicatorElement = useMemo(
    () => (
      <span className="flex items-center justify-center">
        <p className="text-14 !leading-3 text-tertiary">{count}</p>
      </span>
    ),
    [count]
  );

  return <CollapsibleButton isOpen={isOpen} title={t("pull_requests.title")} indicatorElement={indicatorElement} />;
});
