/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// [FORK] work-item-types
import { EIssueServiceType } from "@plane/types";
import type { IProjectIssues } from "@/store/issue/project";
import { ProjectIssues } from "@/store/issue/project";
import type { IIssueRootStore } from "@/store/issue/root.store";
import type { IProjectEpicsFilter } from "./filter.store";

export type IProjectEpics = IProjectIssues;

// [FORK] work-item-types
/**
 * Project epics store. Epics are work items whose type has `is_epic=True`; they
 * reuse the whole project issues machinery but route every request to the
 * `/epics/` API surface by passing the EPICS service type down to the base store.
 */
export class ProjectEpics extends ProjectIssues implements IProjectEpics {
  constructor(_rootStore: IIssueRootStore, issueFilterStore: IProjectEpicsFilter) {
    // [FORK] work-item-types
    super(_rootStore, issueFilterStore, EIssueServiceType.EPICS);
  }
}
