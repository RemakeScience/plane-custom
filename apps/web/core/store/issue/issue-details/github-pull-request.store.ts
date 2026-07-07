/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
// plane imports
import type {
  TGithubPullRequest,
  TGithubPullRequestMap,
  TGithubPullRequestIdMap,
  TIssueServiceType,
} from "@plane/types";
// services
import { IssueService } from "@/services/issue";
// types
import type { IIssueDetail } from "./root.store";

export interface IGithubPullRequestStoreActions {
  addPullRequests: (issueId: string, pullRequests: TGithubPullRequest[]) => void;
  fetchPullRequests: (workspaceSlug: string, projectId: string, issueId: string) => Promise<TGithubPullRequest[]>;
}

export interface IGithubPullRequestStore extends IGithubPullRequestStoreActions {
  // observables
  pullRequests: TGithubPullRequestIdMap;
  pullRequestMap: TGithubPullRequestMap;
  // helper methods
  getPullRequestsByIssueId: (issueId: string) => string[] | undefined;
  getPullRequestById: (prId: string) => TGithubPullRequest | undefined;
}

export class GithubPullRequestStore implements IGithubPullRequestStore {
  // observables
  pullRequests: TGithubPullRequestIdMap = {};
  pullRequestMap: TGithubPullRequestMap = {};
  // root store
  rootIssueDetailStore: IIssueDetail;
  // services
  issueService;

  constructor(rootStore: IIssueDetail, serviceType: TIssueServiceType) {
    makeObservable(this, {
      // observables
      pullRequests: observable,
      pullRequestMap: observable,
      // actions
      addPullRequests: action.bound,
      fetchPullRequests: action,
    });
    // root store
    this.rootIssueDetailStore = rootStore;
    // services
    this.issueService = new IssueService(serviceType);
  }

  // helper methods
  getPullRequestsByIssueId = (issueId: string) => {
    if (!issueId) return undefined;
    return this.pullRequests[issueId] ?? undefined;
  };

  getPullRequestById = (prId: string) => {
    if (!prId) return undefined;
    return this.pullRequestMap[prId] ?? undefined;
  };

  // actions
  addPullRequests = (issueId: string, pullRequests: TGithubPullRequest[]) => {
    runInAction(() => {
      this.pullRequests[issueId] = pullRequests.map((pr) => pr.id);
      pullRequests.forEach((pr) => set(this.pullRequestMap, pr.id, pr));
    });
  };

  fetchPullRequests = async (workspaceSlug: string, projectId: string, issueId: string) => {
    const response = await this.issueService.fetchGithubPullRequests(workspaceSlug, projectId, issueId);
    this.addPullRequests(issueId, response);
    return response;
  };
}
