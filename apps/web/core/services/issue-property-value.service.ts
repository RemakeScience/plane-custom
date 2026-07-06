/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { API_BASE_URL } from "@plane/constants";
import type { TIssuePropertyValues } from "@plane/types";
// services
import { APIService } from "@/services/api.service";

/**
 * Client for reading and bulk-upserting a work item's custom property values.
 */
export class IssuePropertyValueService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async fetch(workspaceSlug: string, projectId: string, issueId: string): Promise<TIssuePropertyValues> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/property-values/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Read custom property values for many work items in a single request.
   * Returns `{ issueId: { propertyId: values[] } }`. Backs the spreadsheet
   * columns without an N+1 per-row fetch.
   */
  async fetchBulk(
    workspaceSlug: string,
    projectId: string,
    issueIds: string[]
  ): Promise<Record<string, TIssuePropertyValues>> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/property-values/`, {
      issue_ids: issueIds,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /**
   * Bulk upsert: `values` maps property id → list of values. Only the
   * properties present in the payload are replaced; the response is the full,
   * refreshed value map for the issue.
   */
  async upsert(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    values: TIssuePropertyValues
  ): Promise<TIssuePropertyValues> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/property-values/`,
      values
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
