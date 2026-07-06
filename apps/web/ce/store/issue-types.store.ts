/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type { TIssueType } from "@plane/types";
// services
import { IssueTypeService } from "@/services/issue-type.service";
// store
import type { RootStore } from "@/plane-web/store/root.store";

export interface IIssueTypesStore {
  // observables
  issueTypeMap: Record<string, TIssueType>;
  projectIssueTypeIdsMap: Record<string, string[]>;
  fetchedMap: Record<string, boolean>;
  // computed actions
  getIssueTypeById: (issueTypeId: string | null | undefined) => TIssueType | undefined;
  getProjectIssueTypeIds: (projectId: string | null | undefined) => string[] | undefined;
  getProjectIssueTypes: (projectId: string | null | undefined, activeOnly?: boolean) => TIssueType[] | undefined;
  getProjectDefaultIssueTypeId: (projectId: string | null | undefined) => string | undefined;
  isIssueTypeEnabledForProject: (projectId: string | null | undefined) => boolean;
  // fetch actions
  fetchProjectIssueTypes: (workspaceSlug: string, projectId: string) => Promise<TIssueType[]>;
  // crud actions
  enableIssueTypes: (workspaceSlug: string, projectId: string) => Promise<TIssueType>;
  createType: (workspaceSlug: string, projectId: string, data: Partial<TIssueType>) => Promise<TIssueType>;
  updateType: (
    workspaceSlug: string,
    projectId: string,
    issueTypeId: string,
    data: Partial<TIssueType>
  ) => Promise<TIssueType | undefined>;
  deleteType: (workspaceSlug: string, projectId: string, issueTypeId: string) => Promise<void>;
  markAsDefault: (workspaceSlug: string, projectId: string, issueTypeId: string) => Promise<void>;
}

export class IssueTypesStore implements IIssueTypesStore {
  // observables
  issueTypeMap: Record<string, TIssueType> = {};
  projectIssueTypeIdsMap: Record<string, string[]> = {};
  fetchedMap: Record<string, boolean> = {};
  // root store
  rootStore: RootStore;
  // service
  issueTypeService: IssueTypeService;

  constructor(_rootStore: RootStore) {
    makeObservable(this, {
      // observables
      issueTypeMap: observable,
      projectIssueTypeIdsMap: observable,
      fetchedMap: observable,
      // fetch actions
      fetchProjectIssueTypes: action,
      // crud actions
      enableIssueTypes: action,
      createType: action,
      updateType: action,
      deleteType: action,
      markAsDefault: action,
    });
    this.rootStore = _rootStore;
    this.issueTypeService = new IssueTypeService();
  }

  /**
   * @description returns an issue type by its id
   */
  getIssueTypeById = computedFn((issueTypeId: string | null | undefined) => {
    if (!issueTypeId) return undefined;
    return this.issueTypeMap[issueTypeId] ?? undefined;
  });

  /**
   * @description returns the issue type ids associated with a project
   */
  getProjectIssueTypeIds = computedFn((projectId: string | null | undefined) => {
    if (!projectId || !this.fetchedMap[projectId]) return undefined;
    return this.projectIssueTypeIdsMap[projectId] ?? [];
  });

  /**
   * @description returns the issue types associated with a project
   * @param activeOnly when true, only active types are returned
   *
   * Not wrapped in `computedFn` because it takes an optional second argument, and
   * mobx-utils' DeepMap requires a consistent argument count across calls.
   * Reactivity still flows through `getProjectIssueTypeIds` and `issueTypeMap`.
   */
  getProjectIssueTypes = (projectId: string | null | undefined, activeOnly = false) => {
    const issueTypeIds = this.getProjectIssueTypeIds(projectId);
    if (!issueTypeIds) return undefined;
    const issueTypes = issueTypeIds
      .map((issueTypeId) => this.issueTypeMap[issueTypeId])
      .filter((issueType): issueType is TIssueType => Boolean(issueType));
    return activeOnly ? issueTypes.filter((issueType) => issueType.is_active) : issueTypes;
  };

  /**
   * @description returns the default issue type id for a project
   */
  getProjectDefaultIssueTypeId = computedFn((projectId: string | null | undefined) => {
    const issueTypes = this.getProjectIssueTypes(projectId);
    return issueTypes?.find((issueType) => issueType.is_default)?.id;
  });

  /**
   * @description whether the Work Item Types feature is enabled on a project
   */
  isIssueTypeEnabledForProject = computedFn((projectId: string | null | undefined) => {
    if (!projectId) return false;
    const project = this.rootStore.projectRoot.project.getProjectById(projectId);
    return Boolean(project?.is_issue_type_enabled);
  });

  /**
   * @description fetches all the issue types of a project
   */
  fetchProjectIssueTypes = async (workspaceSlug: string, projectId: string) => {
    const response = await this.issueTypeService.fetchAll(workspaceSlug, projectId);
    runInAction(() => {
      response.forEach((issueType) => set(this.issueTypeMap, [issueType.id], issueType));
      set(
        this.projectIssueTypeIdsMap,
        [projectId],
        response.map((issueType) => issueType.id)
      );
      set(this.fetchedMap, [projectId], true);
    });
    return response;
  };

  /**
   * @description enables the feature on a project (creates the default type + backfills)
   */
  enableIssueTypes = async (workspaceSlug: string, projectId: string) => {
    const response = await this.issueTypeService.enable(workspaceSlug, projectId);
    runInAction(() => {
      set(this.issueTypeMap, [response.id], response);
      const existingIds = this.projectIssueTypeIdsMap[projectId] ?? [];
      if (!existingIds.includes(response.id)) {
        set(this.projectIssueTypeIdsMap, [projectId], [...existingIds, response.id]);
      }
      set(this.fetchedMap, [projectId], true);
    });
    return response;
  };

  /**
   * @description creates a new issue type in a project
   */
  createType = async (workspaceSlug: string, projectId: string, data: Partial<TIssueType>) => {
    const response = await this.issueTypeService.create(workspaceSlug, projectId, data);
    runInAction(() => {
      set(this.issueTypeMap, [response.id], response);
      const existingIds = this.projectIssueTypeIdsMap[projectId] ?? [];
      set(this.projectIssueTypeIdsMap, [projectId], [...existingIds, response.id]);
      // a newly created default type unsets the others on the server
      if (response.is_default) this.unsetLocalDefaults(projectId, response.id);
    });
    return response;
  };

  /**
   * @description updates an issue type, reverting on failure
   */
  updateType = async (workspaceSlug: string, projectId: string, issueTypeId: string, data: Partial<TIssueType>) => {
    const original = this.issueTypeMap[issueTypeId];
    try {
      runInAction(() => {
        set(this.issueTypeMap, [issueTypeId], { ...original, ...data });
        if (data.is_default) this.unsetLocalDefaults(projectId, issueTypeId);
      });
      return await this.issueTypeService.update(workspaceSlug, projectId, issueTypeId, data);
    } catch (error) {
      runInAction(() => set(this.issueTypeMap, [issueTypeId], original));
      throw error;
    }
  };

  /**
   * @description deletes an issue type from the store and the server
   */
  deleteType = async (workspaceSlug: string, projectId: string, issueTypeId: string) => {
    await this.issueTypeService.remove(workspaceSlug, projectId, issueTypeId);
    runInAction(() => {
      delete this.issueTypeMap[issueTypeId];
      Object.keys(this.projectIssueTypeIdsMap).forEach((key) => {
        set(
          this.projectIssueTypeIdsMap,
          [key],
          (this.projectIssueTypeIdsMap[key] ?? []).filter((id) => id !== issueTypeId)
        );
      });
    });
  };

  /**
   * @description marks an issue type as the project default, reverting on failure
   */
  markAsDefault = async (workspaceSlug: string, projectId: string, issueTypeId: string) => {
    const original = this.issueTypeMap;
    try {
      runInAction(() => {
        this.unsetLocalDefaults(projectId, issueTypeId);
        set(this.issueTypeMap, [issueTypeId, "is_default"], true);
      });
      await this.issueTypeService.markAsDefault(workspaceSlug, projectId, issueTypeId);
    } catch (error) {
      runInAction(() => {
        this.issueTypeMap = original;
      });
      throw error;
    }
  };

  /**
   * Clears the default flag on every project type except `exceptId`.
   */
  private unsetLocalDefaults(projectId: string, exceptId: string) {
    (this.projectIssueTypeIdsMap[projectId] ?? []).forEach((id) => {
      if (id !== exceptId && this.issueTypeMap[id]?.is_default) {
        set(this.issueTypeMap, [id, "is_default"], false);
      }
    });
  }
}
