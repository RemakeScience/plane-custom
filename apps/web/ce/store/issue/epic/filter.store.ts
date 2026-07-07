/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IProjectIssuesFilter } from "@/store/issue/project";
import { ProjectIssuesFilter } from "@/store/issue/project";
import type { IIssueRootStore } from "@/store/issue/root.store";

export type IProjectEpicsFilter = IProjectIssuesFilter;

// [FORK] work-item-types
/**
 * Filter store for project epics. Epics reuse the project issue filters (layout,
 * display filters and properties are persisted per project via ProjectService).
 */
export class ProjectEpicsFilter extends ProjectIssuesFilter implements IProjectEpicsFilter {
  constructor(_rootStore: IIssueRootStore) {
    super(_rootStore);

    // root store
    this.rootIssueStore = _rootStore;
  }
}
