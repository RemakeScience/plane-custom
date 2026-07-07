/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TGithubPRState = "OPEN" | "CLOSED" | "MERGED";

export type TGithubPullRequest = {
  id: string;
  issue: string;
  pr_number: number;
  repository_full_name: string;
  title: string;
  url: string;
  state: TGithubPRState;
  merged: boolean;
  author_login: string;
  ephemeral_env_url: string | null;
  created_at: string;
  updated_at: string;
};

export type TGithubPullRequestMap = {
  [pr_id: string]: TGithubPullRequest;
};

export type TGithubPullRequestIdMap = {
  [issue_id: string]: string[];
};
