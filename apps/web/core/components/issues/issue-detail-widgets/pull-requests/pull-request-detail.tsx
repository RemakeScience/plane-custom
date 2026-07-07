/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { ExternalLink, GitMerge, GitPullRequest, GitPullRequestClosed, Rocket } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { TGithubPRState, TIssueServiceType } from "@plane/types";
import { Tooltip } from "@plane/propel/tooltip";
import { calculateTimeAgo } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { usePlatformOS } from "@/hooks/use-platform-os";

type Props = {
  prId: string;
  issueServiceType: TIssueServiceType;
};

const STATE_META: Record<TGithubPRState, { Icon: typeof GitPullRequest; className: string; labelKey: string }> = {
  OPEN: {
    Icon: GitPullRequest,
    className: "text-green-600 bg-green-500/10",
    labelKey: "pull_requests.state.open",
  },
  MERGED: {
    Icon: GitMerge,
    className: "text-purple-600 bg-purple-500/10",
    labelKey: "pull_requests.state.merged",
  },
  CLOSED: {
    Icon: GitPullRequestClosed,
    className: "text-red-600 bg-red-500/10",
    labelKey: "pull_requests.state.closed",
  },
};

export const GithubPullRequestDetail = observer(function GithubPullRequestDetail(props: Props) {
  const { prId, issueServiceType } = props;
  // translation
  const { t } = useTranslation();
  // store hooks
  const {
    githubPullRequest: { getPullRequestById },
  } = useIssueDetail(issueServiceType);
  const { isMobile } = usePlatformOS();

  const pr = getPullRequestById(prId);
  if (!pr) return null;

  const meta = STATE_META[pr.state] ?? STATE_META.OPEN;
  const { Icon } = meta;

  return (
    <div className="relative flex flex-col gap-1 rounded-md bg-surface-2 p-2.5">
      <div className="flex w-full items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <span className={`mt-0.5 flex items-center gap-1 rounded px-1.5 py-0.5 text-11 ${meta.className}`}>
            <Icon className="size-3 flex-shrink-0" />
            {t(meta.labelKey)}
          </span>
          <Tooltip tooltipContent={pr.title || pr.url} isMobile={isMobile}>
            <a
              href={pr.url}
              target="_blank"
              rel="noopener noreferrer"
              className="min-w-0 truncate text-11 text-primary hover:underline"
            >
              <span className="text-tertiary">{pr.repository_full_name}</span> #{pr.pr_number} — {pr.title}
            </a>
          </Tooltip>
        </div>
        <a
          href={pr.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex flex-shrink-0 items-center justify-center p-1 hover:bg-layer-1"
        >
          <ExternalLink className="size-3 stroke-[1.5] text-secondary" />
        </a>
      </div>

      {pr.ephemeral_env_url && (
        <a
          href={pr.ephemeral_env_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 pl-1 text-11 text-secondary hover:text-primary hover:underline"
        >
          <Rocket className="size-3 flex-shrink-0" />
          {t("pull_requests.preview_link")}
        </a>
      )}

      <p className="pl-1 text-11 text-tertiary">
        {pr.author_login ? `${pr.author_login} · ` : ""}
        {calculateTimeAgo(pr.created_at)}
      </p>
    </div>
  );
});
