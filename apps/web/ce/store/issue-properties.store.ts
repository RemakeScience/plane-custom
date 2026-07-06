/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { set } from "lodash-es";
import { action, makeObservable, observable, runInAction } from "mobx";
import { computedFn } from "mobx-utils";
// plane imports
import type { TIssueProperty, TIssuePropertyOption, TIssuePropertyValues } from "@plane/types";
// services
import { IssuePropertyService } from "@/services/issue-property.service";
import { IssuePropertyValueService } from "@/services/issue-property-value.service";
// store
import type { RootStore } from "@/plane-web/store/root.store";

export interface IIssuePropertiesStore {
  // observables
  propertyMap: Record<string, TIssueProperty>;
  optionMap: Record<string, TIssuePropertyOption>;
  projectPropertyIdsMap: Record<string, string[]>;
  propertyOptionIdsMap: Record<string, string[]>;
  fetchedMap: Record<string, boolean>;
  valuesByIssue: Record<string, TIssuePropertyValues>;
  // getters
  getPropertyById: (propertyId: string | null | undefined) => TIssueProperty | undefined;
  getIssueValues: (issueId: string | null | undefined) => TIssuePropertyValues | undefined;
  getProjectPropertyIds: (projectId: string | null | undefined) => string[] | undefined;
  getTypeProperties: (
    projectId: string | null | undefined,
    typeId: string | null | undefined,
    activeOnly?: boolean
  ) => TIssueProperty[] | undefined;
  getPropertyOptions: (propertyId: string | null | undefined) => TIssuePropertyOption[];
  // fetch
  fetchProjectProperties: (workspaceSlug: string, projectId: string) => Promise<void>;
  fetchBulkValues: (workspaceSlug: string, projectId: string, issueIds: string[]) => Promise<void>;
  setIssueValues: (issueId: string, values: TIssuePropertyValues) => void;
  // property crud
  createProperty: (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    data: Partial<TIssueProperty>
  ) => Promise<TIssueProperty>;
  updateProperty: (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    propertyId: string,
    data: Partial<TIssueProperty>
  ) => Promise<TIssueProperty>;
  deleteProperty: (workspaceSlug: string, projectId: string, typeId: string, propertyId: string) => Promise<void>;
  // option crud
  createOption: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: Partial<TIssuePropertyOption>
  ) => Promise<TIssuePropertyOption>;
  updateOption: (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string,
    data: Partial<TIssuePropertyOption>
  ) => Promise<TIssuePropertyOption>;
  deleteOption: (workspaceSlug: string, projectId: string, propertyId: string, optionId: string) => Promise<void>;
}

export class IssuePropertiesStore implements IIssuePropertiesStore {
  // observables
  propertyMap: Record<string, TIssueProperty> = {};
  optionMap: Record<string, TIssuePropertyOption> = {};
  projectPropertyIdsMap: Record<string, string[]> = {};
  propertyOptionIdsMap: Record<string, string[]> = {};
  fetchedMap: Record<string, boolean> = {};
  valuesByIssue: Record<string, TIssuePropertyValues> = {};
  // root store
  rootStore: RootStore;
  // services
  issuePropertyService: IssuePropertyService;
  issuePropertyValueService: IssuePropertyValueService;

  constructor(_rootStore: RootStore) {
    makeObservable(this, {
      propertyMap: observable,
      optionMap: observable,
      projectPropertyIdsMap: observable,
      propertyOptionIdsMap: observable,
      fetchedMap: observable,
      valuesByIssue: observable,
      fetchProjectProperties: action,
      fetchBulkValues: action,
      setIssueValues: action,
      createProperty: action,
      updateProperty: action,
      deleteProperty: action,
      createOption: action,
      updateOption: action,
      deleteOption: action,
    });
    this.rootStore = _rootStore;
    this.issuePropertyService = new IssuePropertyService();
    this.issuePropertyValueService = new IssuePropertyValueService();
  }

  getPropertyById = computedFn((propertyId: string | null | undefined) =>
    propertyId ? this.propertyMap[propertyId] : undefined
  );

  getIssueValues = computedFn((issueId: string | null | undefined) =>
    issueId ? this.valuesByIssue[issueId] : undefined
  );

  getProjectPropertyIds = computedFn((projectId: string | null | undefined) => {
    if (!projectId || !this.fetchedMap[projectId]) return undefined;
    return this.projectPropertyIdsMap[projectId] ?? [];
  });

  /**
   * Returns the properties of a given type in a project. Not a `computedFn`
   * because of the optional `activeOnly` argument (mobx-utils requires a fixed
   * argument count); reactivity flows through the observable maps.
   */
  getTypeProperties = (projectId: string | null | undefined, typeId: string | null | undefined, activeOnly = false) => {
    const propertyIds = this.getProjectPropertyIds(projectId);
    if (!propertyIds || !typeId) return undefined;
    const properties = propertyIds
      .map((id) => this.propertyMap[id])
      .filter((p): p is TIssueProperty => Boolean(p) && p.issue_type === typeId);
    return activeOnly ? properties.filter((p) => p.is_active) : properties;
  };

  getPropertyOptions = computedFn((propertyId: string | null | undefined) => {
    if (!propertyId) return [];
    return (this.propertyOptionIdsMap[propertyId] ?? [])
      .map((id) => this.optionMap[id])
      .filter((o): o is TIssuePropertyOption => Boolean(o));
  });

  fetchProjectProperties = async (workspaceSlug: string, projectId: string) => {
    const response = await this.issuePropertyService.fetchPropertiesAndOptions(workspaceSlug, projectId);
    runInAction(() => {
      const propertyIds: string[] = [];
      response.forEach((propertyWithOptions) => {
        const { options, ...property } = propertyWithOptions;
        set(this.propertyMap, [property.id], property);
        propertyIds.push(property.id);
        const optionIds = (options ?? []).map((option) => {
          set(this.optionMap, [option.id], option);
          return option.id;
        });
        set(this.propertyOptionIdsMap, [property.id], optionIds);
      });
      set(this.projectPropertyIdsMap, [projectId], propertyIds);
      set(this.fetchedMap, [projectId], true);
    });
  };

  fetchBulkValues = async (workspaceSlug: string, projectId: string, issueIds: string[]) => {
    if (issueIds.length === 0) return;
    const response = await this.issuePropertyValueService.fetchBulk(workspaceSlug, projectId, issueIds);
    runInAction(() => {
      // Seed every requested issue (so those without values resolve to {} and
      // don't refetch), then overlay whatever the server returned.
      issueIds.forEach((issueId) => set(this.valuesByIssue, [issueId], this.valuesByIssue[issueId] ?? {}));
      Object.entries(response ?? {}).forEach(([issueId, values]) => set(this.valuesByIssue, [issueId], values));
    });
  };

  setIssueValues = (issueId: string, values: TIssuePropertyValues) => {
    runInAction(() => set(this.valuesByIssue, [issueId], values));
  };

  createProperty = async (workspaceSlug: string, projectId: string, typeId: string, data: Partial<TIssueProperty>) => {
    const response = await this.issuePropertyService.createProperty(workspaceSlug, projectId, typeId, data);
    runInAction(() => {
      set(this.propertyMap, [response.id], response);
      const ids = this.projectPropertyIdsMap[projectId] ?? [];
      if (!ids.includes(response.id)) set(this.projectPropertyIdsMap, [projectId], [...ids, response.id]);
      set(this.propertyOptionIdsMap, [response.id], []);
    });
    return response;
  };

  updateProperty = async (
    workspaceSlug: string,
    projectId: string,
    typeId: string,
    propertyId: string,
    data: Partial<TIssueProperty>
  ) => {
    const original = this.propertyMap[propertyId];
    try {
      runInAction(() => set(this.propertyMap, [propertyId], { ...original, ...data }));
      return await this.issuePropertyService.updateProperty(workspaceSlug, projectId, typeId, propertyId, data);
    } catch (error) {
      runInAction(() => set(this.propertyMap, [propertyId], original));
      throw error;
    }
  };

  deleteProperty = async (workspaceSlug: string, projectId: string, typeId: string, propertyId: string) => {
    await this.issuePropertyService.removeProperty(workspaceSlug, projectId, typeId, propertyId);
    runInAction(() => {
      const ids = (this.projectPropertyIdsMap[projectId] ?? []).filter((id) => id !== propertyId);
      set(this.projectPropertyIdsMap, [projectId], ids);
      delete this.propertyMap[propertyId];
      delete this.propertyOptionIdsMap[propertyId];
    });
  };

  createOption = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    data: Partial<TIssuePropertyOption>
  ) => {
    const response = await this.issuePropertyService.createOption(workspaceSlug, projectId, propertyId, data);
    runInAction(() => {
      set(this.optionMap, [response.id], response);
      const ids = this.propertyOptionIdsMap[propertyId] ?? [];
      if (!ids.includes(response.id)) set(this.propertyOptionIdsMap, [propertyId], [...ids, response.id]);
    });
    return response;
  };

  updateOption = async (
    workspaceSlug: string,
    projectId: string,
    propertyId: string,
    optionId: string,
    data: Partial<TIssuePropertyOption>
  ) => {
    const original = this.optionMap[optionId];
    try {
      runInAction(() => set(this.optionMap, [optionId], { ...original, ...data }));
      return await this.issuePropertyService.updateOption(workspaceSlug, projectId, propertyId, optionId, data);
    } catch (error) {
      runInAction(() => set(this.optionMap, [optionId], original));
      throw error;
    }
  };

  deleteOption = async (workspaceSlug: string, projectId: string, propertyId: string, optionId: string) => {
    await this.issuePropertyService.removeOption(workspaceSlug, projectId, propertyId, optionId);
    runInAction(() => {
      const ids = (this.propertyOptionIdsMap[propertyId] ?? []).filter((id) => id !== optionId);
      set(this.propertyOptionIdsMap, [propertyId], ids);
      delete this.optionMap[optionId];
    });
  };
}
